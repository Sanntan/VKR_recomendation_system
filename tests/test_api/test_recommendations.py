"""
Тесты для API routes рекомендаций.
"""
import pytest
from uuid import uuid4
from datetime import datetime
from fastapi import status
from tests.test_models_sqlite import TestRecommendations as Recommendations, TestEvents as Events


class TestRecommendationsAPI:
    """Тесты для эндпоинтов рекомендаций."""
    
    def test_get_recommendations_for_student_empty(self, test_client, sample_student):
        """Тест получения пустого списка рекомендаций."""
        response = test_client.get(f"/recommendations/by-student/{sample_student.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 0
    
    def test_get_recommendations_for_student(self, test_client, sample_student, sample_event, db_session):
        """Тест получения рекомендаций для студента."""
        # Создаем рекомендацию
        recommendation = Recommendations(
            student_id=sample_student.id,
            event_id=sample_event.id,
            score=0.95
        )
        db_session.add(recommendation)
        db_session.commit()
        
        # Получаем рекомендации
        response = test_client.get(f"/recommendations/by-student/{sample_student.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["event_id"] == str(sample_event.id)
        assert data[0]["score"] == 0.95
    
    def test_get_recommendations_with_limit(self, test_client, sample_student, db_session):
        """Тест получения рекомендаций с лимитом."""
        # Создаем несколько мероприятий и рекомендаций
        for i in range(5):
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
            
            recommendation = Recommendations(
                student_id=sample_student.id,
                event_id=event.id,
                score=0.9 - i * 0.1
            )
            db_session.add(recommendation)
        db_session.commit()
        
        # Получаем с лимитом
        response = test_client.get(f"/recommendations/by-student/{sample_student.id}?limit=3")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
    
    def test_get_recommendations_sorted_by_score(self, test_client, sample_student, db_session):
        """Тест сортировки рекомендаций по score."""
        # Создаем рекомендации с разными score
        scores = [0.5, 0.9, 0.7, 0.8]
        for score in scores:
            event = Events(
                id=uuid4(),
                title=f"Event {score}",
                is_active=True,
                likes_count=0,
                dislikes_count=0,
                created_at=datetime.now()
            )
            db_session.add(event)
            db_session.flush()
            
            recommendation = Recommendations(
                student_id=sample_student.id,
                event_id=event.id,
                score=score
            )
            db_session.add(recommendation)
        db_session.commit()
        
        # Получаем рекомендации
        response = test_client.get(f"/recommendations/by-student/{sample_student.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Проверяем сортировку (по убыванию score)
        scores_received = [r["score"] for r in data]
        assert scores_received == sorted(scores, reverse=True)

