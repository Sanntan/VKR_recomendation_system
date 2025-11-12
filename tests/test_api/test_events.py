"""
Тесты для API routes мероприятий.
"""
import pytest
from uuid import uuid4
from datetime import date, datetime
from fastapi import status
from tests.test_models_sqlite import TestEvents as Events


class TestEventsAPI:
    """Тесты для эндпоинтов мероприятий."""
    
    def test_list_active_events_empty(self, test_client):
        """Тест получения пустого списка активных мероприятий."""
        response = test_client.get("/events/active")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "events" in data
        assert len(data["events"]) == 0
    
    def test_list_active_events_with_data(self, test_client, sample_event):
        """Тест получения списка активных мероприятий."""
        response = test_client.get("/events/active")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["title"] == "Тестовое мероприятие"
    
    def test_get_event_by_id(self, test_client, sample_event):
        """Тест получения мероприятия по ID."""
        response = test_client.get(f"/events/{sample_event.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(sample_event.id)
        assert data["title"] == "Тестовое мероприятие"
    
    def test_get_event_by_id_not_found(self, test_client):
        """Тест получения несуществующего мероприятия."""
        fake_id = uuid4()
        response = test_client.get(f"/events/{fake_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_like_event(self, test_client, sample_event):
        """Тест лайка мероприятия."""
        initial_likes = sample_event.likes_count
        response = test_client.post(f"/events/{sample_event.id}/like")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["likes_count"] == initial_likes + 1
    
    def test_dislike_event(self, test_client, sample_event):
        """Тест дизлайка мероприятия."""
        initial_dislikes = sample_event.dislikes_count
        response = test_client.post(f"/events/{sample_event.id}/dislike")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["dislikes_count"] == initial_dislikes + 1
    
    def test_list_events_filters_inactive(self, test_client, db_session):
        """Тест фильтрации неактивных мероприятий."""
        from tests.test_models_sqlite import TestEvents as Events
        from datetime import date
        
        # Создаем неактивное мероприятие
        inactive_event = Events(
            id=uuid4(),
            title="Неактивное мероприятие",
            is_active=False,
            likes_count=0,
            dislikes_count=0,
            created_at=datetime.now()
        )
        db_session.add(inactive_event)
        
        # Создаем активное мероприятие
        active_event = Events(
            id=uuid4(),
            title="Активное мероприятие",
            is_active=True,
            likes_count=0,
            dislikes_count=0,
            created_at=datetime.now()
        )
        db_session.add(active_event)
        db_session.commit()
        
        # Проверяем, что возвращается только активное
        response = test_client.get("/events/active")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["title"] == "Активное мероприятие"

