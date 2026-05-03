"""HTTP routes. All business logic lives in server.core; this module only
translates between Pydantic schemas and the core functions.
"""

from __future__ import annotations

from fastapi import APIRouter

from server.api.schemas import EchoRequest, EchoResponse, HealthResponse
from server.core import echo

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/echo", response_model=EchoResponse)
def post_echo(payload: EchoRequest) -> EchoResponse:
    return EchoResponse(message=echo(payload.message))
