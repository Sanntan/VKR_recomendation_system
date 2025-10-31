from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from src.core.database.models import Students
from uuid import UUID

def create_student(db: Session, participant_id: str, institution: str, direction_id: UUID, profile_embedding: list[float] = None):
    student = Students(
        participant_id=participant_id,
        institution=institution,
        direction_id=direction_id,
        profile_embedding=profile_embedding
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student

def get_student_by_participant_id(db: Session, participant_id: str):
    stmt = select(Students).where(Students.participant_id == participant_id)
    return db.execute(stmt).scalar_one_or_none()

def get_all_students(db: Session, limit: int = 100):
    stmt = select(Students).limit(limit)
    return db.execute(stmt).scalars().all()

def update_student_embedding(db: Session, student_id: UUID, embedding: list[float]):
    stmt = (
        update(Students)
        .where(Students.id == student_id)
        .values(profile_embedding=embedding)
    )
    db.execute(stmt)
    db.commit()

def delete_student(db: Session, student_id: UUID):
    db.execute(delete(Students).where(Students.id == student_id))
    db.commit()
    return True
