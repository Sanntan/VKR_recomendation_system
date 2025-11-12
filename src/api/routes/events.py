from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.dependencies import db_dependency
from sqlalchemy import select

from src.api.schemas import EventSchema, EventListResponse, EventBulkRequest
from src.core.database.crud.events import (
    get_active_events,
    get_events_by_clusters,
    get_event_by_id,
    increment_likes,
    increment_dislikes,
)
from src.core.database.models import Events


router = APIRouter()


@router.get("/active", response_model=EventListResponse)
def get_active_events_list(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(db_dependency),
) -> EventListResponse:
    events = get_active_events(db, limit=limit)
    return EventListResponse(events=[EventSchema.model_validate(event) for event in events], total=len(events))


@router.get("/by-clusters", response_model=EventListResponse)
def get_events_for_clusters(
    cluster_ids: List[UUID] = Query(..., description="Список идентификаторов кластеров"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(db_dependency),
) -> EventListResponse:
    events = get_events_by_clusters(db, cluster_ids=cluster_ids, limit=limit)
    return EventListResponse(events=[EventSchema.model_validate(event) for event in events], total=len(events))


@router.post("/bulk", response_model=EventListResponse)
def get_events_bulk(payload: EventBulkRequest, db: Session = Depends(db_dependency)) -> EventListResponse:
    if not payload.ids:
        return EventListResponse(events=[], total=0)

    stmt = select(Events).where(Events.id.in_(payload.ids))
    events = db.execute(stmt).scalars().all()
    events_map = {str(event.id): event for event in events}

    ordered_events = [events_map[str(event_id)] for event_id in payload.ids if str(event_id) in events_map]
    return EventListResponse(events=[EventSchema.model_validate(event) for event in ordered_events], total=len(events))


@router.get("/{event_id}", response_model=EventSchema)
def get_event(event_id: UUID, db: Session = Depends(db_dependency)) -> EventSchema:
    event = get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventSchema.model_validate(event)


@router.post("/{event_id}/like", response_model=EventSchema)
def like_event(event_id: UUID, db: Session = Depends(db_dependency)) -> EventSchema:
    increment_likes(db, event_id)
    event = get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found after like")
    return EventSchema.model_validate(event)


@router.post("/{event_id}/dislike", response_model=EventSchema)
def dislike_event(event_id: UUID, db: Session = Depends(db_dependency)) -> EventSchema:
    increment_dislikes(db, event_id)
    event = get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found after dislike")
    return EventSchema.model_validate(event)

