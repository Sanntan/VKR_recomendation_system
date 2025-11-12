"""
Тесты для CRUD операций с мероприятиями.
"""
import pytest
from uuid import uuid4
from datetime import date, datetime
from tests.test_models_sqlite import TestEvents as Events
from src.core.database.crud.events import (
    create_event,
    get_event_by_id,
    get_active_events,
    increment_likes,
    increment_dislikes
)


class TestEventsCRUD:
    """Тесты для CRUD операций с мероприятиями."""
    
    def test_create_event(self, db_session):
        """Тест создания мероприятия."""
        event = create_event(
            db_session,
            title="Новое мероприятие",
            short_description="Краткое описание",
            description="Полное описание",
            format="онлайн",
            start_date=date.today(),
            end_date=date.today()
        )
        assert event.title == "Новое мероприятие"
        assert event.is_active is True
        assert event.likes_count == 0
        assert event.dislikes_count == 0
    
    def test_get_event_by_id(self, db_session, sample_event):
        """Тест получения мероприятия по ID."""
        event = get_event_by_id(db_session, sample_event.id)
        assert event is not None
        assert event.id == sample_event.id
        assert event.title == "Тестовое мероприятие"
    
    def test_list_active_events(self, db_session):
        """Тест получения списка активных мероприятий."""
        # Создаем активное и неактивное мероприятия
        active = create_event(
            db_session,
            title="Активное"
        )
        # Обновляем одно как неактивное
        inactive = create_event(
            db_session,
            title="Неактивное"
        )
        inactive.is_active = False
        db_session.commit()
        
        events = get_active_events(db_session, limit=10)
        event_ids = [e.id for e in events]
        assert active.id in event_ids
        assert inactive.id not in event_ids
    
    def test_like_event(self, db_session, sample_event):
        """Тест лайка мероприятия."""
        initial_likes = sample_event.likes_count
        increment_likes(db_session, sample_event.id)
        db_session.refresh(sample_event)
        assert sample_event.likes_count == initial_likes + 1
    
    def test_dislike_event(self, db_session, sample_event):
        """Тест дизлайка мероприятия."""
        initial_dislikes = sample_event.dislikes_count
        increment_dislikes(db_session, sample_event.id)
        db_session.refresh(sample_event)
        assert sample_event.dislikes_count == initial_dislikes + 1
    
    def test_delete_event(self, db_session, sample_event):
        """Тест удаления мероприятия."""
        event_id = sample_event.id
        db_session.delete(sample_event)
        db_session.commit()
        
        event = get_event_by_id(db_session, event_id)
        assert event is None

