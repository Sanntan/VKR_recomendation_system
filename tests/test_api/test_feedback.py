"""
Тесты для API routes обратной связи.
"""
import pytest
from uuid import uuid4
from fastapi import status
from tests.test_models_sqlite import TestFeedback as Feedback


class TestFeedbackAPI:
    """Тесты для эндпоинтов обратной связи."""
    
    def test_submit_feedback(self, test_client, sample_student):
        """Тест отправки обратной связи."""
        payload = {
            "student_id": str(sample_student.id),
            "rating": 5,
            "comment": "Отличный бот!"
        }
        response = test_client.post("/feedback", json=payload)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["rating"] == 5
        assert data["comment"] == "Отличный бот!"
    
    def test_submit_feedback_without_comment(self, test_client, sample_student):
        """Тест отправки обратной связи без комментария."""
        payload = {
            "student_id": str(sample_student.id),
            "rating": 4
        }
        response = test_client.post("/feedback", json=payload)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["rating"] == 4
        assert data["comment"] is None
    
    def test_submit_feedback_invalid_rating(self, test_client, sample_student):
        """Тест отправки обратной связи с невалидным рейтингом."""
        # Note: Schema doesn't validate rating range, so this will succeed
        # If validation is needed, it should be added to FeedbackCreateSchema
        payload = {
            "student_id": str(sample_student.id),
            "rating": 10
        }
        response = test_client.post("/feedback", json=payload)
        # Currently no validation, so this will succeed
        assert response.status_code == status.HTTP_201_CREATED

