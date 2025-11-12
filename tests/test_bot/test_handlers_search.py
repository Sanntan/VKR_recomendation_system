"""
Тесты для handlers поиска.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from telegram import Update
from src.bot.handlers.search import (
    show_search_filters,
    handle_search_filter,
    show_next_search_result
)


@pytest.fixture
def mock_update_with_callback():
    """Создает мок Update с callback_query."""
    update = MagicMock(spec=Update)
    callback_query = AsyncMock()
    callback_query.answer = AsyncMock()
    callback_query.edit_message_text = AsyncMock()
    callback_query.data = ""
    update.callback_query = callback_query
    return update


@pytest.mark.asyncio
@patch('src.bot.middlewares.auth_middleware.api_client.get_bot_user', new_callable=AsyncMock)
@patch('src.bot.middlewares.auth_middleware.api_client.update_bot_user_activity', new_callable=AsyncMock)
async def test_show_search_filters(mock_update_activity, mock_get_bot_user, mock_update_with_callback, mock_context):
    """Тест показа фильтров поиска."""
    mock_get_bot_user.return_value = {"is_linked": True, "student": {"id": "test"}}
    mock_update_with_callback.callback_query.answer = AsyncMock()
    await show_search_filters(mock_update_with_callback, mock_context)
    
    mock_update_with_callback.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
@patch('src.bot.middlewares.auth_middleware.api_client.get_bot_user', new_callable=AsyncMock)
@patch('src.bot.middlewares.auth_middleware.api_client.update_bot_user_activity', new_callable=AsyncMock)
async def test_handle_search_filter(mock_update_activity, mock_get_bot_user, mock_update_with_callback, mock_context):
    """Тест обработки фильтра поиска."""
    mock_get_bot_user.return_value = {"is_linked": True, "student": {"id": "test"}}
    mock_context.user_data = {
        'student': {'id': str(uuid4())}
    }
    mock_update_with_callback.callback_query.data = "filter_all"
    mock_update_with_callback.callback_query.answer = AsyncMock()
    
    with patch('src.bot.handlers.search.api_client.get_active_events', new_callable=AsyncMock) as mock_get, \
         patch('src.bot.handlers.search.api_client.check_favorite', new_callable=AsyncMock) as mock_check:
        mock_get.return_value = {
            'events': [
                {
                    'id': str(uuid4()),
                    'title': 'Test Event',
                    'short_description': 'Test',
                    'start_date': '2025-01-20',
                    'format': 'онлайн'
                }
            ],
            'total': 1
        }
        mock_check.return_value = False
        
        await handle_search_filter(mock_update_with_callback, mock_context)
        
        mock_update_with_callback.callback_query.edit_message_text.assert_called_once()

