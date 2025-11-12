from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from src.core.database.models import Feedback
from uuid import UUID

# -------------------------------
# CREATE
# -------------------------------
def create_feedback(db: Session, student_id: UUID, rating: int, comment: str = None):
    """Добавление нового отзыва от студента."""
    from datetime import datetime
    feedback = Feedback(
        student_id=student_id,
        rating=rating,
        comment=comment,
        created_at=datetime.now()
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


# -------------------------------
# READ
# -------------------------------
def get_feedback_by_id(db: Session, feedback_id: int):
    """Получить отзыв по ID."""
    return db.get(Feedback, feedback_id)


def get_feedbacks_by_student(db: Session, student_id: UUID):
    """Получить все отзывы конкретного студента."""
    stmt = select(Feedback).where(Feedback.student_id == student_id)
    return db.execute(stmt).scalars().all()


def get_all_feedbacks(db: Session, limit: int = 100):
    """Получить все отзывы."""
    stmt = select(Feedback).limit(limit)
    return db.execute(stmt).scalars().all()


# -------------------------------
# UPDATE
# -------------------------------
def update_feedback(db: Session, feedback_id: int, rating: int = None, comment: str = None):
    """Обновить оценку или комментарий."""
    values = {}
    if rating is not None:
        values["rating"] = rating
    if comment is not None:
        values["comment"] = comment

    if not values:
        return False

    stmt = (
        update(Feedback)
        .where(Feedback.id == feedback_id)
        .values(**values)
    )
    db.execute(stmt)
    db.commit()
    return True


# -------------------------------
# DELETE
# -------------------------------
def delete_feedback(db: Session, feedback_id: int):
    """Удалить отзыв по ID."""
    feedback = db.get(Feedback, feedback_id)
    if feedback:
        db.delete(feedback)
        db.commit()
        return True
    return False


def delete_all_feedbacks(db: Session):
    """Удалить все отзывы."""
    db.execute(delete(Feedback))
    db.commit()
