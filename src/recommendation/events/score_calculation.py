"""Функции для расчета score между студентами и мероприятиями."""

from __future__ import annotations

import numpy as np
import faiss
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from uuid import UUID

from src.core.database.models import Students, Events, Recommendations
from src.core.database.crud.recommendations import create_recommendation, delete_all_recommendations
from src.recommendation.events.utils import _vector_to_array, _normalize_vector


def calculate_cosine_similarity(
    student_embedding: Optional[list[float] | np.ndarray],
    event_embedding: Optional[list[float] | np.ndarray]
) -> float:
    """
    Рассчитывает косинусное сходство между векторами студента и мероприятия.
    
    Args:
        student_embedding: Вектор профиля студента (384 измерения)
        event_embedding: Вектор мероприятия (384 измерения)
    
    Returns:
        Score от 0 до 1 (1 - максимальное сходство)
    """
    student_vec = _vector_to_array(student_embedding)
    event_vec = _vector_to_array(event_embedding)
    
    if student_vec is None or event_vec is None:
        return 0.0
    
    # Нормализуем векторы
    student_vec = _normalize_vector(student_vec)
    event_vec = _normalize_vector(event_vec)
    
    # Косинусное сходство = скалярное произведение нормализованных векторов
    similarity = np.dot(student_vec, event_vec)
    
    # Ограничиваем значение от 0 до 1
    return max(0.0, min(1.0, float(similarity)))


def calculate_score_for_student_event(
    db: Session,
    student_id: UUID,
    event_id: UUID
) -> Optional[float]:
    """
    Рассчитывает score для конкретной пары студент-мероприятие.
    
    Args:
        db: Сессия базы данных
        student_id: ID студента
        event_id: ID мероприятия
    
    Returns:
        Score или None, если нет векторов
    """
    student = db.get(Students, student_id)
    event = db.get(Events, event_id)
    
    if not student or not event:
        return None
    
    if not student.profile_embedding or not event.vector_embedding:
        return None
    
    score = calculate_cosine_similarity(
        student.profile_embedding,
        event.vector_embedding
    )
    
    return score


def recalculate_scores_for_all_students(db: Session, min_score: float = 0.0, batch_size: int = 1000) -> dict[str, int]:
    """
    Пересчитывает scores для всех студентов и всех активных мероприятий.
    Оптимизированная версия с использованием FAISS и batch операций.
    
    Args:
        db: Сессия базы данных
        min_score: Минимальный score для сохранения рекомендации (по умолчанию 0.0 - сохраняем все)
        batch_size: Размер батча для вставки в БД (по умолчанию 1000)
    
    Returns:
        Словарь со статистикой: {'total_calculated', 'total_saved', 'students_processed', 'events_processed'}
    """
    print("\n🔄 Начало пересчета scores для всех студентов и мероприятий...")
    print("⚡ Используется оптимизированный алгоритм с FAISS и batch операциями")
    
    # Получаем всех студентов с векторами
    print("\n📥 Загрузка данных из БД...")
    students_stmt = select(Students).where(Students.profile_embedding.isnot(None))
    students = list(db.execute(students_stmt).scalars().all())
    
    # Получаем все активные мероприятия с векторами
    events_stmt = select(Events).where(
        Events.is_active == True,
        Events.vector_embedding.isnot(None)
    )
    events = list(db.execute(events_stmt).scalars().all())
    
    if not students:
        print("⚠️  Не найдено студентов с векторами профиля")
        return {
            'total_calculated': 0,
            'total_saved': 0,
            'students_processed': 0,
            'events_processed': 0
        }
    
    if not events:
        print("⚠️  Не найдено активных мероприятий с векторами")
        return {
            'total_calculated': 0,
            'total_saved': 0,
            'students_processed': len(students),
            'events_processed': 0
        }
    
    print(f"📊 Найдено:")
    print(f"   👥 Студентов: {len(students)}")
    print(f"   🎯 Мероприятий: {len(events)}")
    print(f"   📈 Всего пар для расчета: {len(students) * len(events)}")
    
    # Удаляем все существующие рекомендации
    print("\n🗑️  Удаление старых рекомендаций...")
    delete_all_recommendations(db)
    print("✅ Старые рекомендации удалены")
    
    # Подготовка данных для FAISS
    print("\n🔧 Подготовка данных для FAISS индекса...")
    event_vectors = []
    event_ids = []
    
    for event in events:
        vec = _vector_to_array(event.vector_embedding)
        if vec is not None:
            vec = _normalize_vector(vec)
            event_vectors.append(vec)
            event_ids.append(event.id)
    
    if not event_vectors:
        print("⚠️  Не удалось подготовить векторы мероприятий")
        return {
            'total_calculated': 0,
            'total_saved': 0,
            'students_processed': len(students),
            'events_processed': 0
        }
    
    # Создаем FAISS индекс для мероприятий
    vector_dim = event_vectors[0].shape[0]
    events_matrix = np.vstack(event_vectors).astype('float32')
    events_index = faiss.IndexFlatIP(vector_dim)  # Inner Product для косинусного сходства (векторы уже нормализованы)
    events_index.add(events_matrix)
    
    print(f"✅ FAISS индекс создан: {len(event_ids)} мероприятий, размерность {vector_dim}")
    
    # Подготовка векторов студентов
    student_vectors = []
    student_ids = []
    student_participant_ids = []
    
    for student in students:
        vec = _vector_to_array(student.profile_embedding)
        if vec is not None:
            vec = _normalize_vector(vec)
            student_vectors.append(vec)
            student_ids.append(student.id)
            student_participant_ids.append(student.participant_id)
    
    if not student_vectors:
        print("⚠️  Не удалось подготовить векторы студентов")
        return {
            'total_calculated': 0,
            'total_saved': 0,
            'students_processed': 0,
            'events_processed': len(events)
        }
    
    students_matrix = np.vstack(student_vectors).astype('float32')
    
    print(f"✅ Подготовлено {len(student_vectors)} векторов студентов")
    
    # Массовый расчет scores с использованием FAISS
    print("\n🧮 Массовый расчет scores с использованием FAISS...")
    print(f"   Используется batch размер: {batch_size}")
    
    # Вычисляем все scores за один раз (матричное умножение)
    # Результат: матрица [студенты x мероприятия] с scores
    all_scores = np.dot(students_matrix, events_matrix.T)  # Inner product для нормализованных векторов = cosine similarity
    
    # Ограничиваем значения от 0 до 1
    all_scores = np.clip(all_scores, 0.0, 1.0)
    
    total_calculated = all_scores.size
    total_saved = 0
    
    # Batch вставка рекомендаций
    print("💾 Сохранение рекомендаций в БД (batch операции)...")
    recommendations_batch = []
    
    for student_idx, student_id in enumerate(student_ids):
        if (student_idx + 1) % 50 == 0 or student_idx == 0:
            print(f"   Обработка студента {student_idx + 1}/{len(student_ids)}: {student_participant_ids[student_idx]}")
        
        scores_for_student = all_scores[student_idx]
        
        for event_idx, event_id in enumerate(event_ids):
            score = float(scores_for_student[event_idx])
            
            if score >= min_score:
                recommendations_batch.append({
                    'student_id': student_id,
                    'event_id': event_id,
                    'score': score
                })
                
                # Вставляем батчами для оптимизации
                if len(recommendations_batch) >= batch_size:
                    _bulk_insert_recommendations(db, recommendations_batch)
                    total_saved += len(recommendations_batch)
                    recommendations_batch = []
    
    # Вставляем оставшиеся рекомендации
    if recommendations_batch:
        _bulk_insert_recommendations(db, recommendations_batch)
        total_saved += len(recommendations_batch)
    
    print(f"\n✅ Пересчет завершен!")
    print(f"   📊 Рассчитано пар: {total_calculated}")
    print(f"   💾 Сохранено рекомендаций: {total_saved}")
    print(f"   👥 Обработано студентов: {len(students)}")
    print(f"   🎯 Обработано мероприятий: {len(events)}")
    
    return {
        'total_calculated': total_calculated,
        'total_saved': total_saved,
        'students_processed': len(students),
        'events_processed': len(events)
    }


def _bulk_insert_recommendations(db: Session, recommendations: list[dict]) -> None:
    """
    Быстрая вставка рекомендаций батчами.
    
    Args:
        db: Сессия базы данных
        recommendations: Список словарей с ключами 'student_id', 'event_id', 'score'
    """
    if not recommendations:
        return
    
    # Используем bulk_insert_mappings для быстрой вставки
    db.bulk_insert_mappings(Recommendations, recommendations)
    db.commit()


def recalculate_scores_for_student(
    db: Session,
    student_id: UUID,
    min_score: float = 0.0
) -> dict[str, int]:
    """
    Пересчитывает scores для конкретного студента.
    Оптимизированная версия с использованием FAISS.
    
    Args:
        db: Сессия базы данных
        student_id: ID студента
        min_score: Минимальный score для сохранения
    
    Returns:
        Словарь со статистикой
    """
    student = db.get(Students, student_id)
    if not student or not student.profile_embedding:
        return {
            'total_calculated': 0,
            'total_saved': 0,
            'events_processed': 0
        }
    
    # Получаем все активные мероприятия с векторами
    events_stmt = select(Events).where(
        Events.is_active == True,
        Events.vector_embedding.isnot(None)
    )
    events = list(db.execute(events_stmt).scalars().all())
    
    if not events:
        return {
            'total_calculated': 0,
            'total_saved': 0,
            'events_processed': 0
        }
    
    # Удаляем старые рекомендации для этого студента
    db.execute(
        delete(Recommendations).where(Recommendations.student_id == student_id)
    )
    db.commit()
    
    # Подготовка вектора студента
    student_vec = _vector_to_array(student.profile_embedding)
    if student_vec is None:
        return {
            'total_calculated': 0,
            'total_saved': 0,
            'events_processed': 0
        }
    student_vec = _normalize_vector(student_vec).astype('float32').reshape(1, -1)
    
    # Подготовка векторов мероприятий и создание FAISS индекса
    event_vectors = []
    event_ids = []
    
    for event in events:
        vec = _vector_to_array(event.vector_embedding)
        if vec is not None:
            vec = _normalize_vector(vec)
            event_vectors.append(vec)
            event_ids.append(event.id)
    
    if not event_vectors:
        return {
            'total_calculated': 0,
            'total_saved': 0,
            'events_processed': 0
        }
    
    # Создаем FAISS индекс
    vector_dim = event_vectors[0].shape[0]
    events_matrix = np.vstack(event_vectors).astype('float32')
    events_index = faiss.IndexFlatIP(vector_dim)
    events_index.add(events_matrix)
    
    # Вычисляем все scores за один раз
    scores, _ = events_index.search(student_vec, len(event_ids))
    scores = np.clip(scores[0], 0.0, 1.0)
    
    # Сохраняем рекомендации батчем
    recommendations_batch = []
    for event_idx, event_id in enumerate(event_ids):
        score = float(scores[event_idx])
        if score >= min_score:
            recommendations_batch.append({
                'student_id': student_id,
                'event_id': event_id,
                'score': score
            })
    
    if recommendations_batch:
        _bulk_insert_recommendations(db, recommendations_batch)
    
    return {
        'total_calculated': len(events),
        'total_saved': len(recommendations_batch),
        'events_processed': len(events)
    }

