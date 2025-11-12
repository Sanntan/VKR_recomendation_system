from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from src.core.database.models import Favorites


def add_favorite(db: Session, student_id: UUID, event_id: UUID) -> Favorites | None:
    """Добавить мероприятие в избранное."""
    # Проверяем, не добавлено ли уже
    existing = db.execute(
        select(Favorites).where(
            Favorites.student_id == student_id,
            Favorites.event_id == event_id
        )
    ).scalar_one_or_none()
    
    if existing:
        return None  # Уже в избранном
    
    from datetime import datetime
    favorite = Favorites(student_id=student_id, event_id=event_id, created_at=datetime.now())
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return favorite


def remove_favorite(db: Session, student_id: UUID, event_id: UUID) -> bool:
    """Удалить мероприятие из избранного."""
    stmt = delete(Favorites).where(
        Favorites.student_id == student_id,
        Favorites.event_id == event_id
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount > 0


def get_favorites_for_student(db: Session, student_id: UUID, limit: int = 100) -> list[Favorites]:
    """Получить все избранные мероприятия студента."""
    stmt = (
        select(Favorites)
        .where(Favorites.student_id == student_id)
        .order_by(Favorites.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def is_favorite(db: Session, student_id: UUID, event_id: UUID) -> bool:
    """Проверить, находится ли мероприятие в избранном."""
    favorite = db.execute(
        select(Favorites).where(
            Favorites.student_id == student_id,
            Favorites.event_id == event_id
        )
    ).scalar_one_or_none()
    return favorite is not None


def get_favorite_by_id(db: Session, favorite_id: int) -> Favorites | None:
    """Получить избранное по ID."""
    return db.get(Favorites, favorite_id)


def count_favorites_for_student(db: Session, student_id: UUID) -> int:
    """Подсчитать количество избранных мероприятий студента."""
    from sqlalchemy import func
    stmt = select(func.count(Favorites.id)).where(Favorites.student_id == student_id)
    result = db.execute(stmt).scalar()
    return result or 0

