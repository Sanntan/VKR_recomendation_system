from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from src.core.database.models import Directions
from uuid import UUID

def create_direction(db: Session, title: str):
    direction = Directions(title=title)
    db.add(direction)
    db.commit()
    db.refresh(direction)
    return direction

def get_direction_by_id(db: Session, direction_id: UUID):
    return db.get(Directions, direction_id)

def get_all_directions(db: Session, limit: int = 100):
    stmt = select(Directions).limit(limit)
    return db.execute(stmt).scalars().all()

def delete_direction(db: Session, direction_id: UUID):
    db.execute(delete(Directions).where(Directions.id == direction_id))
    db.commit()
    return True

def delete_all_directions(db: Session):
    db.execute(delete(Directions))
    db.commit()
