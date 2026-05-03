"""HTTP routes — all handlers async, all DB I/O via AsyncSession.

The wire layer. Pure-logic transformations live in `server.core`; persistence
goes through SQLAlchemy via the `get_session` dependency. Each route should
stay thin enough to read top-to-bottom in one screen.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server import models
from server.api.schemas import (
    EchoRequest,
    EchoResponse,
    HealthResponse,
    Item,
    ItemCreate,
    Note,
    NoteCreate,
)
from server.core import echo
from server.db import get_session

router = APIRouter()


# ============================================================================
# Health + echo (the original example endpoints)
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/echo", response_model=EchoResponse)
async def post_echo(payload: EchoRequest) -> EchoResponse:
    return EchoResponse(message=echo(payload.message))


# ============================================================================
# Items — example data model #1
# ============================================================================

@router.get("/items", response_model=list[Item])
async def list_items(session: AsyncSession = Depends(get_session)) -> list[models.Item]:
    result = await session.scalars(
        select(models.Item).order_by(models.Item.id.desc())
    )
    return list(result.all())


@router.post("/items", response_model=Item, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate, session: AsyncSession = Depends(get_session)
) -> models.Item:
    item = models.Item(name=payload.name, description=payload.description)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.get("/items/{item_id}", response_model=Item)
async def get_item(
    item_id: int, session: AsyncSession = Depends(get_session)
) -> models.Item:
    item = await session.get(models.Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int, session: AsyncSession = Depends(get_session)
) -> None:
    item = await session.get(models.Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    await session.delete(item)
    await session.commit()


# ============================================================================
# Notes — example data model #2
# ============================================================================

@router.get("/notes", response_model=list[Note])
async def list_notes(session: AsyncSession = Depends(get_session)) -> list[models.Note]:
    result = await session.scalars(
        select(models.Note).order_by(models.Note.id.desc())
    )
    return list(result.all())


@router.post("/notes", response_model=Note, status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteCreate, session: AsyncSession = Depends(get_session)
) -> models.Note:
    note = models.Note(title=payload.title, body=payload.body)
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note


@router.get("/notes/{note_id}", response_model=Note)
async def get_note(
    note_id: int, session: AsyncSession = Depends(get_session)
) -> models.Note:
    note = await session.get(models.Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: int, session: AsyncSession = Depends(get_session)
) -> None:
    note = await session.get(models.Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    await session.delete(note)
    await session.commit()
