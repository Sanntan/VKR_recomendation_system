"""
Тесты для API routes избранного.
"""
import pytest
from uuid import uuid4
from datetime import datetime
from fastapi import status
from tests.test_models_sqlite import TestFavorites as Favorites, TestEvents as Events


class TestFavoritesAPI:
    """Тесты для эндпоинтов избранного."""
    
    def test_add_favorite(self, test_client, sample_student, sample_event):
        """Тест добавления мероприятия в избранное."""
        response = test_client.post(
            f"/favorites/{sample_student.id}/{sample_event.id}"
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["student_id"] == str(sample_student.id)
        assert data["event_id"] == str(sample_event.id)
    
    def test_add_favorite_duplicate(self, test_client, sample_student, sample_event, db_session):
        """Тест добавления дубликата в избранное."""
        # Добавляем первый раз
        response = test_client.post(
            f"/favorites/{sample_student.id}/{sample_event.id}"
        )
        assert response.status_code == status.HTTP_201_CREATED
        
        # Пытаемся добавить второй раз
        response = test_client.post(
            f"/favorites/{sample_student.id}/{sample_event.id}"
        )
        assert response.status_code == status.HTTP_409_CONFLICT
    
    def test_remove_favorite(self, test_client, sample_student, sample_event, db_session):
        """Тест удаления из избранного."""
        # Сначала добавляем
        favorite = Favorites(
            student_id=sample_student.id,
            event_id=sample_event.id
        )
        db_session.add(favorite)
        db_session.commit()
        
        # Удаляем
        response = test_client.delete(
            f"/favorites/{sample_student.id}/{sample_event.id}"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_remove_favorite_not_found(self, test_client, sample_student, sample_event):
        """Тест удаления несуществующего избранного."""
        response = test_client.delete(
            f"/favorites/{sample_student.id}/{sample_event.id}"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_list_favorites_for_student(self, test_client, sample_student, sample_event, db_session):
        """Тест получения списка избранного для студента."""
        # Добавляем избранное
        favorite = Favorites(
            student_id=sample_student.id,
            event_id=sample_event.id
        )
        db_session.add(favorite)
        db_session.commit()
        
        # Получаем список
        response = test_client.get(f"/favorites/by-student/{sample_student.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["event"]["id"] == str(sample_event.id)
    
    def test_get_favorites_count(self, test_client, sample_student, sample_event, db_session):
        """Тест получения количества избранного."""
        # Добавляем несколько избранных
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
            
            favorite = Favorites(
                student_id=sample_student.id,
                event_id=event.id
            )
            db_session.add(favorite)
        db_session.commit()
        
        # Проверяем количество
        response = test_client.get(f"/favorites/by-student/{sample_student.id}/count")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 3
    
    def test_check_favorite(self, test_client, sample_student, sample_event, db_session):
        """Тест проверки наличия в избранном."""
        # Проверяем до добавления
        response = test_client.get(
            f"/favorites/{sample_student.id}/{sample_event.id}/check"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_favorite"] is False
        
        # Добавляем
        favorite = Favorites(
            student_id=sample_student.id,
            event_id=sample_event.id
        )
        db_session.add(favorite)
        db_session.commit()
        
        # Проверяем после добавления
        response = test_client.get(
            f"/favorites/{sample_student.id}/{sample_event.id}/check"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_favorite"] is True

