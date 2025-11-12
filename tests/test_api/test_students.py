"""
Тесты для API routes студентов.
"""
import pytest
from uuid import uuid4
from datetime import datetime
from fastapi import status
from tests.test_models_sqlite import TestStudents as Students


class TestStudentsAPI:
    """Тесты для эндпоинтов студентов."""
    
    def test_list_students_empty(self, test_client):
        """Тест получения пустого списка студентов."""
        response = test_client.get("/students")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "students" in data
        assert len(data["students"]) == 0
    
    def test_list_students_with_data(self, test_client, sample_student):
        """Тест получения списка студентов с данными."""
        response = test_client.get("/students")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["students"]) == 1
        assert data["students"][0]["participant_id"] == "test_student_001"
    
    def test_get_student_by_id(self, test_client, sample_student):
        """Тест получения студента по ID."""
        response = test_client.get(f"/students/{sample_student.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(sample_student.id)
        assert data["participant_id"] == "test_student_001"
    
    def test_get_student_by_id_not_found(self, test_client):
        """Тест получения несуществующего студента."""
        fake_id = uuid4()
        response = test_client.get(f"/students/{fake_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_get_student_by_participant_id(self, test_client, sample_student):
        """Тест получения студента по participant_id."""
        response = test_client.get(f"/students/by-participant/{sample_student.participant_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["participant_id"] == "test_student_001"
    
    def test_get_student_by_participant_id_not_found(self, test_client):
        """Тест получения студента по несуществующему participant_id."""
        response = test_client.get("/students/by-participant/nonexistent")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_list_students_with_pagination(self, test_client, db_session, sample_direction):
        """Тест пагинации списка студентов."""
        # Создаем несколько студентов
        for i in range(5):
            student = Students(
                id=uuid4(),
                participant_id=f"test_student_{i:03d}",
                direction_id=sample_direction.id,
                created_at=datetime.now()
            )
            db_session.add(student)
        db_session.commit()
        
        # Тест первой страницы
        response = test_client.get("/students?limit=2&offset=0")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["students"]) == 2
        
        # Тест второй страницы
        response = test_client.get("/students?limit=2&offset=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["students"]) == 2

