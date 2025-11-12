from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from src.api.dependencies import db_dependency
from src.api.schemas import (
    StudentSchema,
    DirectionSchema,
    StudentListResponse,
    StudentProfileUpdateSchema
)
from src.core.database.models import Students, Directions
from src.core.database.crud.students import update_student_profile_embedding_from_competencies
from src.recommendation.events.score_calculation import recalculate_scores_for_student


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


@router.get("", response_model=StudentListResponse)
def list_students(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_dependency),
) -> StudentListResponse:
    total = db.execute(select(func.count()).select_from(Students)).scalar_one()
    stmt = (
        select(Students)
        .options(selectinload(Students.direction))
        .order_by(Students.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    students = db.execute(stmt).scalars().all()
    return StudentListResponse(
        students=[_build_student(student) for student in students],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.put("/{student_id}/profile", response_model=StudentSchema)
def update_student_profile(
    student_id: UUID,
    payload: StudentProfileUpdateSchema,
    db: Session = Depends(db_dependency)
) -> StudentSchema:
    """
    Обновляет профильный вектор студента на основе компетенций.
    Компетенции не сохраняются в БД, используются только для генерации вектора профиля.
    После обновления вектора профиля автоматически пересчитываются рекомендации для студента.

    Args:
        student_id: ID студента
        payload: Данные для обновления (компетенции и опционально специальность)

    Returns:
        Обновленный объект StudentSchema с обновленным profile_embedding
    """
    try:
        # Обновляем вектор профиля на основе компетенций
        student = update_student_profile_embedding_from_competencies(
            db=db,
            student_id=student_id,
            competencies=payload.competencies,
            specialty=payload.specialty
        )

        # Пересчитываем рекомендации для этого студента
        recalculate_scores_for_student(db, student_id, min_score=0.0)

        # Загружаем направление для ответа
        db.refresh(student, ["direction"])

        return _build_student(student)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении профиля: {str(e)}"
        )

