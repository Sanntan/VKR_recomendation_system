from __future__ import annotations

from datetime import datetime, date
from typing import Optional, Sequence
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class DirectionSchema(BaseModel):
    id: UUID
    title: Optional[str]
    cluster_id: Optional[UUID]
    model_config = ConfigDict(from_attributes=True)


class StudentSchema(BaseModel):
    id: UUID
    participant_id: str
    institution: Optional[str]
    direction: Optional[DirectionSchema] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class StudentListResponse(BaseModel):
    students: Sequence[StudentSchema]
    total: int
    limit: int
    offset: int


class BotUserSchema(BaseModel):
    telegram_id: int
    username: Optional[str]
    email: Optional[str]
    is_linked: bool
    last_activity: Optional[datetime]
    student: Optional[StudentSchema] = None
    model_config = ConfigDict(from_attributes=True)


class BotUserCreateSchema(BaseModel):
    telegram_id: int
    student_id: UUID
    username: Optional[str] = None
    email: Optional[str] = None


class EventSchema(BaseModel):
    id: UUID
    title: str
    short_description: Optional[str] = None
    description: Optional[str] = None
    format: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    link: Optional[str] = None
    image_url: Optional[str] = None
    likes_count: int = 0
    dislikes_count: int = 0
    is_active: bool = True
    created_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class EventListResponse(BaseModel):
    events: Sequence[EventSchema]
    total: int = Field(..., description="Общее число найденных мероприятий до применения лимита")


class EventBulkRequest(BaseModel):
    ids: Sequence[UUID]


class RecommendationSchema(BaseModel):
    id: int
    student_id: UUID
    event_id: UUID
    score: Optional[float] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FeedbackCreateSchema(BaseModel):
    student_id: UUID
    rating: int
    comment: Optional[str] = None


class FeedbackResponseSchema(BaseModel):
    id: int
    student_id: UUID
    rating: int
    comment: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FavoriteSchema(BaseModel):
    id: int
    student_id: UUID
    event_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FavoriteWithEventSchema(BaseModel):
    id: int
    student_id: UUID
    event_id: UUID
    created_at: datetime
    event: EventSchema
    model_config = ConfigDict(from_attributes=True)
