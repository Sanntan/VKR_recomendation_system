from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import db_dependency
from src.api.schemas import FavoriteSchema, FavoriteWithEventSchema, EventSchema
from src.core.database.crud.favorites import (
    add_favorite,
    remove_favorite,
    get_favorites_for_student,
    is_favorite,
    count_favorites_for_student,
)
from src.core.database.crud.events import get_event_by_id


router = APIRouter()


@router.post("/{student_id}/{event_id}", response_model=FavoriteSchema, status_code=status.HTTP_201_CREATED)
def add_favorite_endpoint(
    student_id: UUID,
    event_id: UUID,
    db: Session = Depends(db_dependency),
) -> FavoriteSchema:
    """Добавить мероприятие в избранное."""
    favorite = add_favorite(db, student_id=student_id, event_id=event_id)
    if not favorite:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Мероприятие уже в избранном"
        )
    return FavoriteSchema.model_validate(favorite)


@router.delete("/{student_id}/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite_endpoint(
    student_id: UUID,
    event_id: UUID,
    db: Session = Depends(db_dependency),
) -> None:
    """Удалить мероприятие из избранного."""
    removed = remove_favorite(db, student_id=student_id, event_id=event_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Мероприятие не найдено в избранном"
        )


@router.get("/by-student/{student_id}", response_model=List[FavoriteWithEventSchema])
def get_favorites_for_student_endpoint(
    student_id: UUID,
    limit: int = 100,
    db: Session = Depends(db_dependency),
) -> List[FavoriteWithEventSchema]:
    """Получить все избранные мероприятия студента с полной информацией о мероприятиях."""
    favorites = get_favorites_for_student(db, student_id=student_id, limit=limit)
    
    result = []
    for favorite in favorites:
        event = get_event_by_id(db, favorite.event_id)
        if event:
            result.append(
                FavoriteWithEventSchema(
                    id=favorite.id,
                    student_id=favorite.student_id,
                    event_id=favorite.event_id,
                    created_at=favorite.created_at,
                    event=EventSchema.model_validate(event)
                )
            )
        # Если мероприятие удалено, пропускаем его (можно было бы удалить из favorites, но оставляем для истории)
    
    return result


@router.get("/by-student/{student_id}/count", response_model=dict)
def get_favorites_count_endpoint(
    student_id: UUID,
    db: Session = Depends(db_dependency),
) -> dict:
    """Получить количество избранных мероприятий студента."""
    count = count_favorites_for_student(db, student_id=student_id)
    return {"student_id": str(student_id), "count": count}


@router.get("/{student_id}/{event_id}/check", response_model=dict)
def check_favorite_endpoint(
    student_id: UUID,
    event_id: UUID,
    db: Session = Depends(db_dependency),
) -> dict:
    """Проверить, находится ли мероприятие в избранном."""
    is_fav = is_favorite(db, student_id=student_id, event_id=event_id)
    return {"student_id": str(student_id), "event_id": str(event_id), "is_favorite": is_fav}

