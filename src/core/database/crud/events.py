from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from src.core.database.models import Events
from uuid import UUID
from datetime import date

def create_event(
    db: Session,
    title: str,
    description: str = None,
    short_description: str = None,
    format: str = None,
    start_date: date = None,
    end_date: date = None,
    link: str = None,
    image_url: str = None,
    vector_embedding: list[float] = None
):
    event = Events(
        title=title,
        description=description,
        short_description=short_description,
        format=format,
        start_date=start_date,
        end_date=end_date,
        link=link,
        image_url=image_url,
        vector_embedding=vector_embedding
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

def get_event_by_id(db: Session, event_id: UUID):
    return db.get(Events, event_id)

def get_all_events(db: Session, limit: int = 100):
    stmt = select(Events).limit(limit)
    return db.execute(stmt).scalars().all()

def get_active_events(db: Session, limit: int = 100):
    stmt = select(Events).where(Events.is_active == True).limit(limit)
    return db.execute(stmt).scalars().all()

def update_event_info(db: Session, event_id: UUID, **kwargs):
    stmt = (
        update(Events)
        .where(Events.id == event_id)
        .values(**kwargs)
        .execution_options(synchronize_session="fetch")
    )
    db.execute(stmt)
    db.commit()

def delete_event(db: Session, event_id: UUID):
    db.execute(delete(Events).where(Events.id == event_id))
    db.commit()
    return True

def delete_all_events(db: Session):
    db.execute(delete(Events))
    db.commit()
