from __future__ import annotations
from datetime import date
from sqlalchemy.orm import Session

from src.core.database.crud.events import create_event, update_event_info
from src.core.database.models import Events
from src.recommendation.events.mapping import CSVEvent, compute_is_active
from src.recommendation.events.llm_generator import generate_short_and_format

def upsert_event(db: Session, csv_event: CSVEvent, vector=None):
    """Добавляет или обновляет мероприятие по ссылке."""
    short, fmt = generate_short_and_format(csv_event.title, csv_event.description)
    is_active = compute_is_active(date.today(), csv_event.start_date, csv_event.end_date)

    existing = db.query(Events).filter(Events.link == csv_event.link).first()

    data = dict(
        title=csv_event.title,
        description=csv_event.description,
        short_description=short,
        format=fmt,
        start_date=csv_event.start_date,
        end_date=csv_event.end_date,
        link=csv_event.link,
        image_url=csv_event.image_url,
        vector_embedding=vector,
        is_active=is_active,
    )

    if existing:
        update_event_info(db, existing.id, **data)
        return existing.id, "updated"
    new_event = create_event(db=db, **data)
    return new_event.id, "inserted"
