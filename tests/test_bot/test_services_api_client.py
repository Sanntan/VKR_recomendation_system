"""
Тесты для API клиента бота.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from src.bot.services.api_client import APIClient, APIClientError
import httpx


class TestAPIClient:
    """Тесты для APIClient."""
    
    @pytest.fixture
    def api_client(self):
        """Создает экземпляр APIClient."""
        return APIClient(base_url="http://test-api.com")
    
    @pytest.mark.asyncio
    async def test_get_student_by_participant(self, api_client):
        """Тест получения студента по participant_id."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': str(uuid4()),
            'participant_id': 'test_001'
        }
        mock_response.raise_for_status = MagicMock()
        mock_response.content = b'{"id":"test","participant_id":"test_001"}'
        
        with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await api_client.get_student_by_participant("test_001")
            
            assert result['participant_id'] == 'test_001'
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_recommendations(self, api_client):
        """Тест получения рекомендаций."""
        student_id = uuid4()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'id': str(uuid4()), 'score': 0.9}
        ]
        mock_response.raise_for_status = MagicMock()
        mock_response.content = b'[{"id":"test","score":0.9}]'
        
        with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await api_client.get_recommendations(student_id)
            
            assert len(result) == 1
            assert result[0]['score'] == 0.9
    
    @pytest.mark.asyncio
    async def test_add_favorite(self, api_client):
        """Тест добавления в избранное."""
        student_id = uuid4()
        event_id = uuid4()
        
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'student_id': str(student_id),
            'event_id': str(event_id)
        }
        mock_response.raise_for_status = MagicMock()
        mock_response.content = b'{"student_id":"' + str(student_id).encode() + b'","event_id":"' + str(event_id).encode() + b'"}'
        
        with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await api_client.add_favorite(student_id, event_id)
            
            assert result['student_id'] == str(student_id)
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_api_client_error(self, api_client):
        """Тест обработки ошибки API."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_request_obj = MagicMock()
        mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
            "Not found", request=mock_request_obj, response=mock_response
        ))
        
        with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            # 404 should return None, not raise error
            result = await api_client.get_student_by_participant("nonexistent")
            assert result is None

