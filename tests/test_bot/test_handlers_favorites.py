"""
Тесты для handlers избранного.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from telegram import Update, CallbackQuery
from src.bot.handlers.favorites import (
    show_personal_cabinet,
    show_favorites,
    handle_favorite_action,
    show_next_favorite
)


@pytest.fixture
def mock_update_with_callback():
    """Создает мок Update с callback_query."""
    update = MagicMock(spec=Update)
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.answer = AsyncMock()
    callback_query.edit_message_text = AsyncMock()
    callback_query.data = ""
    update.callback_query = callback_query
    update.message = None
    return update


@pytest.mark.asyncio
@patch('src.bot.middlewares.auth_middleware.api_client.get_bot_user', new_callable=AsyncMock)
@patch('src.bot.middlewares.auth_middleware.api_client.update_bot_user_activity', new_callable=AsyncMock)
async def test_show_personal_cabinet(mock_update_activity, mock_get_bot_user, mock_update_with_callback, mock_context):
    """Тест показа личного кабинета."""
    mock_get_bot_user.return_value = {"is_linked": True, "student": {"id": str(uuid4())}}
    mock_context.user_data = {
        'student': {
            'id': str(uuid4()),
            'participant_id': 'test_001',
            'direction': {'title': 'Тестовое направление'}
        }
    }
    mock_update_with_callback.callback_query.answer = AsyncMock()
    
    with patch('src.bot.handlers.favorites.api_client.get_favorites_count', new_callable=AsyncMock) as mock_count:
        mock_count.return_value = 5
        
        await show_personal_cabinet(mock_update_with_callback, mock_context)
        
        mock_update_with_callback.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
@patch('src.bot.middlewares.auth_middleware.api_client.get_bot_user', new_callable=AsyncMock)
@patch('src.bot.middlewares.auth_middleware.api_client.update_bot_user_activity', new_callable=AsyncMock)
async def test_show_favorites_empty(mock_update_activity, mock_get_bot_user, mock_update_with_callback, mock_context):
    """Тест показа пустого списка избранного."""
    mock_get_bot_user.return_value = {"is_linked": True, "student": {"id": str(uuid4())}}
    mock_context.user_data = {
        'student': {'id': str(uuid4())}
    }
    mock_update_with_callback.callback_query.answer = AsyncMock()
    
    with patch('src.bot.handlers.favorites.api_client.get_favorites', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = []
        
        await show_favorites(mock_update_with_callback, mock_context)
        
        mock_update_with_callback.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update_with_callback.callback_query.edit_message_text.call_args
        text = call_args[1].get('text', '') or call_args[0][0] if call_args[0] else ''
        assert "нет избранных" in text.lower()


@pytest.mark.asyncio
@patch('src.bot.middlewares.auth_middleware.api_client.get_bot_user', new_callable=AsyncMock)
@patch('src.bot.middlewares.auth_middleware.api_client.update_bot_user_activity', new_callable=AsyncMock)
async def test_handle_favorite_action_add(mock_update_activity, mock_get_bot_user, mock_update_with_callback, mock_context):
    """Тест добавления в избранное."""
    mock_get_bot_user.return_value = {"is_linked": True, "student": {"id": str(uuid4())}}
    student_id = uuid4()
    event_id = uuid4()
    mock_context.user_data = {
        'student': {'id': str(student_id)}
    }
    mock_update_with_callback.callback_query.data = f"add_favorite_{event_id}"
    mock_update_with_callback.callback_query.answer = AsyncMock()
    
    with patch('src.bot.handlers.favorites.api_client.add_favorite', new_callable=AsyncMock) as mock_add, \
         patch('src.bot.handlers.favorites.api_client.check_favorite', new_callable=AsyncMock) as mock_check:
        mock_add.return_value = {}
        mock_check.return_value = True
        
        await handle_favorite_action(mock_update_with_callback, mock_context)
        
        # answer вызывается несколько раз (в начале и при успехе)
        assert mock_update_with_callback.callback_query.answer.call_count >= 1
        mock_add.assert_called_once()


@pytest.mark.asyncio
@patch('src.bot.middlewares.auth_middleware.api_client.get_bot_user', new_callable=AsyncMock)
@patch('src.bot.middlewares.auth_middleware.api_client.update_bot_user_activity', new_callable=AsyncMock)
async def test_handle_favorite_action_remove(mock_update_activity, mock_get_bot_user, mock_update_with_callback, mock_context):
    """Тест удаления из избранного."""
    mock_get_bot_user.return_value = {"is_linked": True, "student": {"id": str(uuid4())}}
    student_id = uuid4()
    event_id = uuid4()
    mock_context.user_data = {
        'student': {'id': str(student_id)}
    }
    mock_update_with_callback.callback_query.data = f"remove_favorite_{event_id}"
    mock_update_with_callback.callback_query.answer = AsyncMock()
    
    with patch('src.bot.handlers.favorites.api_client.remove_favorite', new_callable=AsyncMock) as mock_remove, \
         patch('src.bot.handlers.favorites.api_client.check_favorite', new_callable=AsyncMock) as mock_check:
        mock_remove.return_value = None
        mock_check.return_value = False
        
        await handle_favorite_action(mock_update_with_callback, mock_context)
        
        # answer вызывается несколько раз (в начале и при успехе)
        assert mock_update_with_callback.callback_query.answer.call_count >= 1
        mock_remove.assert_called_once()

