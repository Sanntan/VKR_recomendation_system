from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, text
from src.core.database.models import BotUsers, Students
from uuid import UUID
from typing import Optional

def create_bot_user(db: Session, telegram_id: int, student_id: UUID, username: str = None, email: str = None):
    """Создание нового пользователя бота."""
    bot_user = BotUsers(
        telegram_id=telegram_id,
        student_id=student_id,
        username=username,
        email=email,
        is_linked=True
    )
    db.add(bot_user)
    db.commit()
    db.refresh(bot_user)
    return bot_user

def get_bot_user_by_telegram_id(db: Session, telegram_id: int):
    """Получить пользователя бота по Telegram ID."""
    stmt = select(BotUsers).where(BotUsers.telegram_id == telegram_id)
    return db.execute(stmt).scalar_one_or_none()

def get_bot_user_with_student(db: Session, telegram_id: int):
    """Получить пользователя бота с информацией о студенте."""
    stmt = (
        select(BotUsers)
        .join(Students, BotUsers.student_id == Students.id)
        .where(BotUsers.telegram_id == telegram_id)
    )
    return db.execute(stmt).scalar_one_or_none()

def update_bot_user_activity(db: Session, telegram_id: int):
    """Обновить время последней активности."""
    stmt = (
        update(BotUsers)
        .where(BotUsers.telegram_id == telegram_id)
        .values(last_activity=text("NOW()"))
    )
    db.execute(stmt)
    db.commit()

def delete_bot_user(db: Session, telegram_id: int):
    """Удалить пользователя бота."""
    db.execute(delete(BotUsers).where(BotUsers.telegram_id == telegram_id))
    db.commit()
    return True


