from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.api.dependencies import db_dependency
from src.api.schemas import StudentSchema, DirectionSchema
from src.core.database.models import Students, Directions


router = APIRouter()


def _build_direction(direction: Directions | None) -> DirectionSchema | None:
    if not direction:
        return None
    return DirectionSchema(
        id=direction.id,
        title=direction.title,
        cluster_id=direction.cluster_id,
    )


def _build_student(student: Students) -> StudentSchema:
    return StudentSchema(
        id=student.id,
        participant_id=student.participant_id,
        institution=student.institution,
        direction=_build_direction(student.direction),
        created_at=student.created_at,
    )


def _load_student_by_participant_id(db: Session, participant_id: str) -> Students | None:
    stmt = (
        select(Students)
        .options(selectinload(Students.direction))
        .where(Students.participant_id == participant_id)
    )
    return db.execute(stmt).scalar_one_or_none()


@router.get("/by-participant/{participant_id}", response_model=StudentSchema)
def get_student_by_participant(participant_id: str, db: Session = Depends(db_dependency)) -> StudentSchema:
    student = _load_student_by_participant_id(db, participant_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return _build_student(student)


@router.get("/{student_id}", response_model=StudentSchema)
def get_student(student_id: UUID, db: Session = Depends(db_dependency)) -> StudentSchema:
    stmt = (
        select(Students)
        .options(selectinload(Students.direction))
        .where(Students.id == student_id)
    )
    student = db.execute(stmt).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return _build_student(student)

