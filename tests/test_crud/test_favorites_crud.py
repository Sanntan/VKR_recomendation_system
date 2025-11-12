"""
Тесты для CRUD операций с избранным.
"""
import pytest
from uuid import uuid4
from datetime import datetime
from tests.test_models_sqlite import TestFavorites as Favorites, TestEvents as Events
from src.core.database.crud.favorites import (
    add_favorite,
    remove_favorite,
    get_favorites_for_student,
    is_favorite,
    count_favorites_for_student
)


class TestFavoritesCRUD:
    """Тесты для CRUD операций с избранным."""
    
    def test_add_favorite(self, db_session, sample_student, sample_event):
        """Тест добавления в избранное."""
        favorite = add_favorite(db_session, sample_student.id, sample_event.id)
        assert favorite is not None
        assert favorite.student_id == sample_student.id
        assert favorite.event_id == sample_event.id
    
    def test_add_favorite_duplicate(self, db_session, sample_student, sample_event):
        """Тест добавления дубликата."""
        # Первое добавление
        favorite1 = add_favorite(db_session, sample_student.id, sample_event.id)
        assert favorite1 is not None
        
        # Второе добавление должно вернуть None
        favorite2 = add_favorite(db_session, sample_student.id, sample_event.id)
        assert favorite2 is None
    
    def test_remove_favorite(self, db_session, sample_student, sample_event):
        """Тест удаления из избранного."""
        # Добавляем
        add_favorite(db_session, sample_student.id, sample_event.id)
        
        # Удаляем
        removed = remove_favorite(db_session, sample_student.id, sample_event.id)
        assert removed is True
        
        # Проверяем, что удалено
        assert is_favorite(db_session, sample_student.id, sample_event.id) is False
    
    def test_remove_favorite_not_found(self, db_session, sample_student, sample_event):
        """Тест удаления несуществующего избранного."""
        removed = remove_favorite(db_session, sample_student.id, sample_event.id)
        assert removed is False
    
    def test_get_favorites_for_student(self, db_session, sample_student, sample_event):
        """Тест получения избранного для студента."""
        # Добавляем несколько избранных
        add_favorite(db_session, sample_student.id, sample_event.id)
        
        favorites = get_favorites_for_student(db_session, sample_student.id)
        assert len(favorites) == 1
        assert favorites[0].event_id == sample_event.id
    
    def test_is_favorite(self, db_session, sample_student, sample_event):
        """Тест проверки наличия в избранном."""
        # До добавления
        assert is_favorite(db_session, sample_student.id, sample_event.id) is False
        
        # После добавления
        add_favorite(db_session, sample_student.id, sample_event.id)
        assert is_favorite(db_session, sample_student.id, sample_event.id) is True
    
    def test_count_favorites_for_student(self, db_session, sample_student):
        """Тест подсчета избранного."""
        # Создаем несколько мероприятий и добавляем в избранное
        for i in range(3):
            event = Events(
                id=uuid4(),
                title=f"Event {i}",
                is_active=True,
                likes_count=0,
                dislikes_count=0,
                created_at=datetime.now()
            )
            db_session.add(event)
            db_session.flush()
            add_favorite(db_session, sample_student.id, event.id)
        
        count = count_favorites_for_student(db_session, sample_student.id)
        assert count == 3

