from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from src.core.database.models import Recommendations
from uuid import UUID

# -------------------------------
# CREATE
# -------------------------------
def create_recommendation(db: Session, student_id: UUID, event_id: UUID, score: float = None):
    """Добавление рекомендации для студента."""
    rec = Recommendations(
        student_id=student_id,
        event_id=event_id,
        score=score
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


# -------------------------------
# READ
# -------------------------------
def get_recommendation_by_id(db: Session, rec_id: int):
    """Получить рекомендацию по ID."""
    return db.get(Recommendations, rec_id)


def get_recommendations_for_student(db: Session, student_id: UUID, limit: int = 10):
    """Получить все рекомендации для конкретного студента."""
    stmt = (
        select(Recommendations)
        .where(Recommendations.student_id == student_id)
        .order_by(Recommendations.score.desc())
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def get_all_recommendations(db: Session, limit: int = 100):
    """Получить все рекомендации."""
    stmt = select(Recommendations).limit(limit)
    return db.execute(stmt).scalars().all()


# -------------------------------
# UPDATE
# -------------------------------
def update_recommendation_score(db: Session, rec_id: int, new_score: float):
    """Обновить значение score."""
    stmt = (
        update(Recommendations)
        .where(Recommendations.id == rec_id)
        .values(score=new_score)
    )
    db.execute(stmt)
    db.commit()


# -------------------------------
# DELETE
# -------------------------------
def delete_recommendation(db: Session, rec_id: int):
    """Удалить конкретную рекомендацию."""
    rec = db.get(Recommendations, rec_id)
    if rec:
        db.delete(rec)
        db.commit()
        return True
    return False


def delete_all_recommendations(db: Session):
    """Удалить все рекомендации."""
    db.execute(delete(Recommendations))
    db.commit()
