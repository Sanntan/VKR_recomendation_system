from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.api.dependencies import db_dependency
from src.api.schemas import BotUserSchema, BotUserCreateSchema, StudentSchema, DirectionSchema
from src.core.database.models import BotUsers, Students, Directions
from src.core.database.crud import bot_users as bot_users_crud


router = APIRouter()


def _build_direction_schema(direction: Directions | None) -> DirectionSchema | None:
    if not direction:
        return None
    return DirectionSchema(
        id=direction.id,
        title=direction.title,
        cluster_id=direction.cluster_id,
    )


def _build_student_schema(student: Students | None) -> StudentSchema | None:
    if not student:
        return None
    return StudentSchema(
        id=student.id,
        participant_id=student.participant_id,
        institution=student.institution,
        direction=_build_direction_schema(student.direction),
        created_at=student.created_at,
    )


def _build_bot_user_schema(bot_user: BotUsers) -> BotUserSchema:
    return BotUserSchema(
        telegram_id=bot_user.telegram_id,
        username=bot_user.username,
        email=bot_user.email,
        is_linked=bot_user.is_linked,
        last_activity=bot_user.last_activity,
        student=_build_student_schema(bot_user.student),
    )


def _load_bot_user(db: Session, telegram_id: int) -> BotUsers | None:
    stmt = (
        select(BotUsers)
        .options(
            selectinload(BotUsers.student).selectinload(Students.direction),
        )
        .where(BotUsers.telegram_id == telegram_id)
    )
    return db.execute(stmt).scalar_one_or_none()


@router.get("/users/{telegram_id}", response_model=BotUserSchema)
def get_bot_user(telegram_id: int, db: Session = Depends(db_dependency)) -> BotUserSchema:
    bot_user = _load_bot_user(db, telegram_id)
    if not bot_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot user not found")
    return _build_bot_user_schema(bot_user)


@router.post("/users", response_model=BotUserSchema, status_code=status.HTTP_201_CREATED)
def create_bot_user(payload: BotUserCreateSchema, db: Session = Depends(db_dependency)) -> BotUserSchema:
    existing = _load_bot_user(db, payload.telegram_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bot user already exists",
        )

    student = db.get(Students, payload.student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    bot_user = bot_users_crud.create_bot_user(
        db=db,
        telegram_id=payload.telegram_id,
        student_id=payload.student_id,
        username=payload.username,
        email=payload.email,
    )
    db.refresh(bot_user)
    bot_user.student = student  # type: ignore[assignment]
    return _build_bot_user_schema(bot_user)


@router.post("/users/{telegram_id}/activity", status_code=status.HTTP_204_NO_CONTENT)
def update_activity(telegram_id: int, db: Session = Depends(db_dependency)) -> None:
    bot_user = bot_users_crud.get_bot_user_by_telegram_id(db, telegram_id)
    if not bot_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot user not found")
    bot_users_crud.update_bot_user_activity(db, telegram_id)


@router.delete("/users/{telegram_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bot_user(telegram_id: int, db: Session = Depends(db_dependency)) -> None:
    bot_user = bot_users_crud.get_bot_user_by_telegram_id(db, telegram_id)
    if not bot_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot user not found")
    bot_users_crud.delete_bot_user(db, telegram_id)

