from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from src.core.database.models import CategoryDirections
from uuid import UUID

def create_category_direction(db: Session, category_id: UUID, direction_id: UUID):
    """Создание связи категория ↔ направление."""
    link = CategoryDirections(category_id=category_id, direction_id=direction_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def get_all_category_directions(db: Session):
    """Получить все связи категория ↔ направление."""
    stmt = select(CategoryDirections)
    return db.execute(stmt).scalars().all()


def delete_category_direction(db: Session, link_id: int):
    """Удалить связь по ID."""
    link = db.get(CategoryDirections, link_id)
    if link:
        db.delete(link)
        db.commit()
        return True
    return False


def delete_all_category_directions(db: Session):
    """Удалить все связи категория ↔ направление."""
    db.execute(delete(CategoryDirections))
    db.commit()
