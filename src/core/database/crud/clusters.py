from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from src.core.database.models import Clusters
from uuid import UUID

def create_cluster(db: Session, title: str, centroid=None):
    cluster = Clusters(title=title, centroid=centroid)
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster

def get_all_clusters(db: Session):
    stmt = select(Clusters)
    return db.execute(stmt).scalars().all()

def delete_cluster(db: Session, cluster_id: UUID):
    db.execute(delete(Clusters).where(Clusters.id == cluster_id))
    db.commit()
