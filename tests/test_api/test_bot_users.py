"""
Тесты для API routes пользователей бота.
"""
import pytest
from uuid import uuid4
from fastapi import status
from src.core.database.models import BotUsers


class TestBotUsersAPI:
    """Тесты для эндпоинтов пользователей бота."""
    
    def test_get_bot_user(self, test_client, sample_bot_user):
        """Тест получения пользователя бота."""
        response = test_client.get(f"/bot/users/{sample_bot_user.telegram_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["telegram_id"] == sample_bot_user.telegram_id
        assert data["student"] is not None
        assert data["student"]["id"] == str(sample_bot_user.student_id)
    
    def test_get_bot_user_not_found(self, test_client):
        """Тест получения несуществующего пользователя бота."""
        response = test_client.get("/bot/users/999999999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_link_bot_user(self, test_client, sample_student):
        """Тест привязки пользователя бота к студенту."""
        payload = {
            "telegram_id": 987654321,
            "student_id": str(sample_student.id),
            "username": "new_user"
        }
        response = test_client.post("/bot/users", json=payload)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["telegram_id"] == 987654321
        assert data["student"]["id"] == str(sample_student.id)
    
    def test_update_bot_user_activity(self, test_client, sample_bot_user):
        """Тест обновления активности пользователя."""
        response = test_client.post(f"/bot/users/{sample_bot_user.telegram_id}/activity")
        assert response.status_code == status.HTTP_204_NO_CONTENT

