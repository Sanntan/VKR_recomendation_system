"""
Тесты для CRUD операций со студентами.
"""
import pytest
from uuid import uuid4
from datetime import datetime
from tests.test_models_sqlite import TestStudents as Students
from src.core.database.crud.students import (
    create_student,
    get_student_by_participant_id,
    get_all_students,
    delete_student
)


class TestStudentsCRUD:
    """Тесты для CRUD операций со студентами."""
    
    def test_create_student(self, db_session, sample_direction):
        """Тест создания студента."""
        student = create_student(
            db_session,
            participant_id="new_student_001",
            institution="Новый вуз",
            direction_id=sample_direction.id
        )
        assert student.participant_id == "new_student_001"
        assert student.institution == "Новый вуз"
        assert student.direction_id == sample_direction.id
    
    def test_get_student_by_id(self, db_session, sample_student):
        """Тест получения студента по ID через модель."""
        student = db_session.get(Students, sample_student.id)
        assert student is not None
        assert student.id == sample_student.id
        assert student.participant_id == "test_student_001"
    
    def test_get_student_by_id_not_found(self, db_session):
        """Тест получения несуществующего студента."""
        fake_id = uuid4()
        student = db_session.get(Students, fake_id)
        assert student is None
    
    def test_get_student_by_participant_id(self, db_session, sample_student):
        """Тест получения студента по participant_id."""
        student = get_student_by_participant_id(db_session, "test_student_001")
        assert student is not None
        assert student.participant_id == "test_student_001"
    
    def test_list_students(self, db_session, sample_direction):
        """Тест получения списка студентов."""
        # Создаем несколько студентов
        for i in range(3):
            create_student(
                db_session,
                participant_id=f"student_{i:03d}",
                institution="Test",
                direction_id=sample_direction.id
            )
        
        students = get_all_students(db_session, limit=10)
        assert len(students) >= 3
    
    def test_update_student_embedding(self, db_session, sample_student):
        """Тест обновления эмбеддинга студента."""
        from src.core.database.crud.students import update_student_embedding
        import json
        
        # Для SQLite конвертируем embedding в строку JSON
        embedding = [0.1] * 384
        embedding_str = json.dumps(embedding)
        update_student_embedding(db_session, sample_student.id, embedding)
        
        # Проверяем в БД
        student = db_session.get(Students, sample_student.id)
        # В SQLite embedding хранится как строка
        assert student.profile_embedding is not None or isinstance(student.profile_embedding, str)
    
    def test_delete_student(self, db_session, sample_student):
        """Тест удаления студента."""
        student_id = sample_student.id
        delete_student(db_session, student_id)
        
        # Проверяем, что удален
        student = db_session.get(Students, student_id)
        assert student is None

