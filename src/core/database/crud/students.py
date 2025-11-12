from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from src.core.database.models import Students
from uuid import UUID
from typing import Optional, Dict
import numpy as np

def create_student(
    db: Session,
    participant_id: str,
    institution: str,
    direction_id: UUID,
    profile_embedding: list[float] = None,
    competencies: Optional[Dict[str, int]] = None
):
    """
    Создает нового студента.

    Args:
        db: Сессия базы данных
        participant_id: ID участника
        institution: Название института
        direction_id: ID направления подготовки
        profile_embedding: Вектор профиля (если не указан и указаны компетенции, будет вычислен автоматически)
        competencies: Словарь компетенций {название: т-балл} - используется только для генерации вектора профиля

    Returns:
        Созданный объект Students
    """
    # Если указаны компетенции, но не указан вектор, вычисляем его
    if competencies and profile_embedding is None:
        from src.recommendation.students.profile_generator import update_profile_embedding_from_competencies
        from src.core.database.crud.directions import get_direction_by_id
        
        # Получаем название специальности
        specialty = None
        if direction_id:
            direction = get_direction_by_id(db, direction_id)
            if direction:
                specialty = direction.title
        
        # Генерируем вектор профиля на основе компетенций
        embedding = update_profile_embedding_from_competencies(specialty, competencies)
        if embedding is not None:
            profile_embedding = embedding.tolist()
            print(f"✅ Вектор профиля для студента {participant_id} сгенерирован на основе компетенций")

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
    """
    Обновляет профильный вектор студента.

    Args:
        db: Сессия базы данных
        student_id: ID студента
        embedding: Вектор профиля
    """
    stmt = (
        update(Students)
        .where(Students.id == student_id)
        .values(profile_embedding=embedding)
    )
    db.execute(stmt)
    db.commit()


def update_student_profile_embedding_from_competencies(
    db: Session,
    student_id: UUID,
    competencies: Dict[str, int],
    specialty: Optional[str] = None
) -> Students:
    """
    Обновляет профильный вектор студента на основе компетенций.
    Компетенции не сохраняются в БД, используются только для генерации вектора профиля.

    Args:
        db: Сессия базы данных
        student_id: ID студента
        competencies: Словарь компетенций {название: т-балл} - используется для генерации вектора профиля
        specialty: Название специальности (если нужно обновить направление и использовать в векторизации)

    Returns:
        Обновленный объект Students с обновленным profile_embedding
    """
    student = db.get(Students, student_id)
    if not student:
        raise ValueError(f"Студент с ID {student_id} не найден")

    # Обновляем направление, если указана специальность
    if specialty:
        from src.core.database.crud.directions import get_direction_by_title
        direction = get_direction_by_title(db, specialty)
        if direction:
            student.direction_id = direction.id
            print(f"✅ Направление студента {student.participant_id} обновлено: {specialty}")

    # Генерируем вектор профиля на основе компетенций
    from src.recommendation.students.profile_generator import update_profile_embedding_from_competencies

    # Получаем название специальности
    specialty_name = specialty
    if not specialty_name:
        # Загружаем направление, если оно не загружено
        if student.direction_id:
            from src.core.database.models import Directions
            direction = db.get(Directions, student.direction_id)
            if direction:
                specialty_name = direction.title

    # Генерируем новый вектор профиля на основе компетенций
    embedding = update_profile_embedding_from_competencies(specialty_name, competencies)
    if embedding is not None:
        student.profile_embedding = embedding.tolist()
        print(f"✅ Профильный вектор студента {student.participant_id} обновлен на основе компетенций")
    else:
        raise ValueError(f"Не удалось сгенерировать вектор профиля для студента {student.participant_id}")

    db.commit()
    db.refresh(student)
    return student


def get_student_by_id(db: Session, student_id: UUID) -> Optional[Students]:
    """
    Получает студента по ID.

    Args:
        db: Сессия базы данных
        student_id: ID студента

    Returns:
        Объект Students или None
    """
    return db.get(Students, student_id)


def delete_student(db: Session, student_id: UUID):
    """
    Удаляет студента по ID.

    Args:
        db: Сессия базы данных
        student_id: ID студента

    Returns:
        True если удаление успешно
    """
    db.execute(delete(Students).where(Students.id == student_id))
    db.commit()
    return True
