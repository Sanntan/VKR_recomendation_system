from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from src.core.database.models import EventCategories
from uuid import UUID

def create_event_category(db: Session, event_id: UUID, category_id: UUID):
    """Создать связь мероприятие ↔ категория."""
    link = EventCategories(event_id=event_id, category_id=category_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def get_all_event_categories(db: Session):
    """Получить все связи мероприятие ↔ категория."""
    stmt = select(EventCategories)
    return db.execute(stmt).scalars().all()


def delete_event_category(db: Session, link_id: int):
    """Удалить связь по ID."""
    link = db.get(EventCategories, link_id)
    if link:
        db.delete(link)
        db.commit()
        return True
    return False


def delete_all_event_categories(db: Session):
    """Удалить все связи мероприятие ↔ категория."""
    db.execute(delete(EventCategories))
    db.commit()
