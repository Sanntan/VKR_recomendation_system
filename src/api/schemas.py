from __future__ import annotations

from datetime import datetime, date
from typing import Optional, Sequence, Dict
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator


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


class StudentProfileUpdateSchema(BaseModel):
    """
    Схема для обновления профильного вектора студента на основе компетенций.
    Компетенции не сохраняются в БД, используются только для генерации вектора профиля.
    """
    competencies: Dict[str, int] = Field(
        ...,
        description="Словарь компетенций: название компетенции -> т-балл (200-800). Используется для генерации вектора профиля.",
        examples=[{
            "Анализ информации": 650,
            "Планирование": 720,
            "Коммуникация": 350,
            "Лидерство": 450,
            "Креативность": 680
        }]
    )
    specialty: Optional[str] = Field(
        None,
        description="Название специальности (направления подготовки). Если указано, обновит направление студента и будет использовано при генерации вектора профиля."
    )

    @field_validator('competencies')
    @classmethod
    def validate_competencies(cls, v: Dict[str, int]) -> Dict[str, int]:
        """Валидация т-баллов компетенций."""
        for competency_name, t_score in v.items():
            if not isinstance(t_score, int):
                raise ValueError(f"Т-балл для '{competency_name}' должен быть целым числом")
            if not (200 <= t_score <= 800):
                raise ValueError(
                    f"Т-балл для '{competency_name}' должен быть в диапазоне 200-800, получено: {t_score}"
                )
        return v

