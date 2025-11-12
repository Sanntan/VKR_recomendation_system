"""
Тесты для обработки ошибок API.
"""
import pytest
from fastapi import status
from src.core.exceptions import NotFoundError, ValidationError


class TestErrorHandling:
    """Тесты для обработки ошибок."""
    
    def test_not_found_error_response(self, test_client):
        """Тест ответа на ошибку 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = test_client.get(f"/students/{fake_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "error" in data
        assert data["error"] is True
    
    def test_validation_error_response(self, test_client):
        """Тест ответа на ошибку валидации."""
        # Отправляем невалидные данные
        response = test_client.post("/feedback", json={
            "student_id": "invalid-uuid",
            "rating": 10  # Должно быть 1-5
        })
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]
        data = response.json()
        assert "error" in data or "detail" in data

