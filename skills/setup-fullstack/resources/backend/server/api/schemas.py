"""Pydantic v2 request / response models.

The schemas ARE the contract. Adding fields here automatically updates the
generated OpenAPI spec at /docs and /openapi.json.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class EchoRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class EchoResponse(BaseModel):
    message: str
