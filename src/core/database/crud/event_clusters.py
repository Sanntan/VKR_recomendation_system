from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from src.core.database.models import EventClusters
from uuid import UUID

def add_event_to_cluster(db: Session, event_id: UUID, cluster_id: UUID):
    rel = EventClusters(event_id=event_id, cluster_id=cluster_id)
    db.add(rel)
    db.commit()
    return rel

def remove_event_from_cluster(db: Session, event_id: UUID, cluster_id: UUID):
    db.execute(
        delete(EventClusters).where(EventClusters.event_id == event_id, EventClusters.cluster_id == cluster_id)
    )
    db.commit()
