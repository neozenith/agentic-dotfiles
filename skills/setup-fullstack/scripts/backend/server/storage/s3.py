"""S3-flavored `StorageBackend` — works against AWS S3 and MinIO.

MinIO targets the S3 wire protocol, so a single boto3-driven implementation
covers both. The only deployment-time differences are:

  * `endpoint_url` — empty for AWS, `http://minio:9000` (or similar) for MinIO.
  * `addressing_style` — MinIO requires `path` style, AWS works with `auto`.
  * Region — MinIO ignores it but boto3 still requires a non-empty value, so
    we default to "us-east-1" if unset (the boto3 default).

Sync boto3 is wrapped in `asyncio.to_thread` because the call volume is tiny
(one upload per backup interval, one download per cold start). Adding
`aioboto3` would mean an extra dependency for almost no concurrency benefit.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, cast

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from server.storage.base import (
    ObjectInfo,
    ObjectMetadata,
    ObjectNotFoundError,
    StorageBackend,
)

# Errors S3 returns when the requested key does not exist. boto3 normalizes
# most of these to "404" / "NoSuchKey", but MinIO has been observed returning
# "NotFound" verbatim. We treat all four as "missing" and re-raise our
# protocol-defined ObjectNotFoundError.
_MISSING_ERROR_CODES = frozenset({"NoSuchKey", "NotFound", "404", "NoSuchBucket"})


@dataclass(slots=True)
class S3Config:
    """Connection parameters for `S3Backend`. Built by the factory from env vars."""

    bucket: str
    region: str = "us-east-1"
    endpoint_url: str | None = None
    # MinIO needs `path`. AWS works with `auto` (and historically `virtual` for
    # legacy regions). Default `auto` so AWS works out of the box.
    addressing_style: str = "auto"


class S3Backend(StorageBackend):
    """`StorageBackend` backed by AWS S3 (or any S3-API-compatible service).

    The boto3 client is constructed eagerly at init time so config errors
    surface immediately rather than on first use. Credentials follow boto3's
    default chain (env vars → ~/.aws/credentials → instance metadata).
    """

    def __init__(self, config: S3Config) -> None:
        self._bucket = config.bucket
        # botocore-stubs defines `s3=` as a private TypedDict (`_S3Dict`) whose
        # name we can't safely import. Cast at the boundary — the runtime
        # accepts a plain dict.
        boto_config = BotoConfig(
            signature_version="s3v4",
            s3=cast(Any, {"addressing_style": config.addressing_style}),
        )
        # boto3.client returns a dynamically-typed object; mypy with
        # boto3-stubs/mypy-boto3-s3 narrows S3 ops, but the constructor
        # itself is `Any`. The stub package is installed; we just keep
        # the local annotation generic to avoid leaking stub-only types
        # into runtime imports.
        self._client = boto3.client(
            "s3",
            region_name=config.region,
            endpoint_url=config.endpoint_url,
            config=boto_config,
        )

    async def put_object(self, key: str, data: bytes) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
        )

    async def get_object(self, key: str) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._client.get_object,
                Bucket=self._bucket,
                Key=key,
            )
        except ClientError as exc:
            if _is_missing(exc):
                raise ObjectNotFoundError(key) from exc
            raise
        body = response["Body"]
        # `read()` is sync on the StreamingBody; bounce off the loop.
        return await asyncio.to_thread(body.read)

    async def head_object(self, key: str) -> ObjectMetadata:
        try:
            response = await asyncio.to_thread(
                self._client.head_object,
                Bucket=self._bucket,
                Key=key,
            )
        except ClientError as exc:
            if _is_missing(exc):
                raise ObjectNotFoundError(key) from exc
            raise
        # ETag arrives quoted on the wire ("...") — strip the quotes for sanity.
        etag = str(response.get("ETag", "")).strip('"')
        return ObjectMetadata(
            key=key,
            size=int(response["ContentLength"]),
            last_modified=response["LastModified"],
            etag=etag,
        )

    async def list_objects(self, prefix: str = "") -> list[ObjectInfo]:
        # ListObjectsV2 is paginated; for our use case (a few backup files)
        # one page is more than enough. If we ever go past 1000 objects with
        # the same prefix we'll switch to a paginator.
        response = await asyncio.to_thread(
            self._client.list_objects_v2,
            Bucket=self._bucket,
            Prefix=prefix,
        )
        contents = response.get("Contents", [])
        entries = [
            ObjectInfo(
                key=str(item["Key"]),
                size=int(item["Size"]),
                last_modified=item["LastModified"],
            )
            for item in contents
        ]
        entries.sort(key=lambda e: e.key)
        return entries


def _is_missing(exc: ClientError) -> bool:
    code = exc.response.get("Error", {}).get("Code", "")
    status = str(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", ""))
    return code in _MISSING_ERROR_CODES or status == "404"
