import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, InlineKeyboardMarkup
from src.bot.handlers.recommendations import show_recommendations, handle_recommendation_feedback, \
    show_next_recommendation
from datetime import datetime, timedelta
from uuid import uuid4


@pytest.fixture
def mock_update_with_callback():
    """Создает мок Update с callback_query."""
    update = MagicMock(spec=Update)
    update.callback_query = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.answer = AsyncMock()
    return update


@pytest.mark.asyncio
@patch('src.bot.middlewares.auth_middleware.api_client.get_bot_user', new_callable=AsyncMock)
@patch('src.bot.middlewares.auth_middleware.api_client.update_bot_user_activity', new_callable=AsyncMock)
async def test_show_recommendations(mock_update_activity, mock_get_bot_user, mock_update_with_callback):
    """Тестирует показ рекомендаций."""
    mock_get_bot_user.return_value = {"is_linked": True, "student": {"id": str(uuid4())}}
    mock_context = MagicMock()
    mock_context.user_data = {
        'student': {'id': str(uuid4())}
    }
    mock_update_with_callback.callback_query.answer = AsyncMock()
    
    with patch('src.bot.handlers.recommendations.api_client.get_recommendations', new_callable=AsyncMock) as mock_get, \
         patch('src.bot.handlers.recommendations.api_client.get_events_bulk', new_callable=AsyncMock) as mock_bulk, \
         patch('src.bot.handlers.recommendations.api_client.check_favorite', new_callable=AsyncMock) as mock_check:
        event_id = str(uuid4())
        event_data = {
            'id': event_id,
            'title': 'Test Event',
            'short_description': 'Test',
            'start_date': '2025-01-20',
            'format': 'онлайн',
            'link': 'https://example.com',
            'likes_count': 0,
            'dislikes_count': 0
        }
        mock_get.return_value = [
            {
                'id': 1,
                'event_id': event_id
            }
        ]
        mock_bulk.return_value = {'events': [event_data]}
        mock_check.return_value = False
        
        await show_recommendations(mock_update_with_callback, mock_context)

    assert mock_update_with_callback.callback_query.edit_message_text.called

    # Проверяем, что данные сохранились в user_data
    assert 'current_recommendations' in mock_context.user_data
    assert 'current_recommendation_index' in mock_context.user_data

    # Проверяем, что был передан правильный текст
    call_args = mock_update_with_callback.callback_query.edit_message_text.call_args
    # Аргументы могут быть в call_args[0] (позиционные) или call_args[1] (именованные)
    if call_args[0]:  # позиционные аргументы
        text = call_args[0][0]
    else:  # именованные аргументы
        text = call_args[1].get('text', '')

    assert "🎯" in text  # Проверяем что это карточка мероприятия


@pytest.mark.asyncio
@patch('src.bot.middlewares.auth_middleware.api_client.get_bot_user', new_callable=AsyncMock)
@patch('src.bot.middlewares.auth_middleware.api_client.update_bot_user_activity', new_callable=AsyncMock)
async def test_handle_recommendation_feedback_like(mock_update_activity, mock_get_bot_user, mock_update_with_callback):
    """Тестирует обработку лайка рекомендации."""
    mock_get_bot_user.return_value = {"is_linked": True, "student": {"id": "test"}}
    mock_context = MagicMock()
    mock_context.user_data = {}

    event_id = str(uuid4())
    mock_update_with_callback.callback_query.data = f"like_{event_id}"
    mock_update_with_callback.callback_query.answer = AsyncMock()
    mock_context.user_data = {
        'student': {'id': str(uuid4())},
        'recommendations_events': {event_id: {'id': event_id, 'title': 'Test'}}
    }

    with patch('src.bot.handlers.recommendations.api_client.like_event', new_callable=AsyncMock) as mock_like, \
         patch('src.bot.handlers.recommendations.api_client.check_favorite', new_callable=AsyncMock) as mock_check:
        mock_like.return_value = {'id': event_id, 'title': 'Test'}
        mock_check.return_value = False
        
        await handle_recommendation_feedback(mock_update_with_callback, mock_context)

    # Проверяем, что answer был вызван с правильным сообщением
    # Note: answer is called twice - once at the start (line 190) and once with the message (line 202)
    answer_calls = mock_update_with_callback.callback_query.answer.call_args_list
    # Check that the message was passed in one of the calls (as positional arg)
    message_found = any(
        call[0] and len(call[0]) > 0 and call[0][0] == "Спасибо! Учтем ваши предпочтения 👍"
        for call in answer_calls
    )
    assert message_found, "Expected answer call with thank you message"


@pytest.mark.asyncio
@patch('src.bot.middlewares.auth_middleware.api_client.get_bot_user', new_callable=AsyncMock)
@patch('src.bot.middlewares.auth_middleware.api_client.update_bot_user_activity', new_callable=AsyncMock)
async def test_handle_recommendation_feedback_dislike(mock_update_activity, mock_get_bot_user, mock_update_with_callback):
    """Тестирует обработку дизлайка рекомендации."""
    mock_get_bot_user.return_value = {"is_linked": True, "student": {"id": "test"}}
    mock_context = MagicMock()
    mock_context.user_data = {}

    event_id = str(uuid4())
    mock_update_with_callback.callback_query.data = f"dislike_{event_id}"
    mock_update_with_callback.callback_query.answer = AsyncMock()
    mock_context.user_data = {
        'student': {'id': str(uuid4())},
        'current_recommendations': [{'event_id': event_id}]
    }

    with patch('src.bot.handlers.recommendations.api_client.dislike_event', new_callable=AsyncMock) as mock_dislike, \
         patch('src.bot.handlers.recommendations.show_next_recommendation', new_callable=AsyncMock) as mock_next:
        mock_dislike.return_value = None
        
        await handle_recommendation_feedback(mock_update_with_callback, mock_context)
        
        # При dislike вызывается show_next_recommendation, а не answer с сообщением
        mock_next.assert_called_once()


@pytest.mark.asyncio
@patch('src.bot.middlewares.auth_middleware.api_client.get_bot_user', new_callable=AsyncMock)
@patch('src.bot.middlewares.auth_middleware.api_client.update_bot_user_activity', new_callable=AsyncMock)
async def test_show_next_recommendation(mock_update_activity, mock_get_bot_user, mock_update_with_callback):
    """Тестирует показ следующей рекомендации."""
    mock_get_bot_user.return_value = {"is_linked": True, "student": {"id": "test"}}
    mock_context = MagicMock()

    # Используем полные тестовые данные как в реальном коде
    mock_context.user_data = {
        'current_recommendations': [
            {
                'id': 1,
                'event_id': str(uuid4()),
                'event': {
                    'id': str(uuid4()),
                    'title': 'Event 1',
                    'start_date': (datetime.now() + timedelta(days=5)).isoformat(),
                    'format': 'офлайн (Центр компетенций, ауд. 202)',
                    'link': 'https://example.com/event1'
                }
            },
            {
                'id': 2,
                'event_id': str(uuid4()),
                'event': {
                    'id': str(uuid4()),
                    'title': 'Event 2',
                    'start_date': (datetime.now() + timedelta(days=3)).isoformat(),
                    'format': 'онлайн (Zoom)',
                    'link': 'https://example.com/event2'
                }
            }
        ],
        'current_recommendation_index': 0
    }
    mock_update_with_callback.callback_query.answer = AsyncMock()

    await show_next_recommendation(mock_update_with_callback, mock_context)

    # Проверяем, что был вызван edit_message_text
    assert mock_update_with_callback.callback_query.edit_message_text.called

    # Проверяем, что индекс обновился
    assert mock_context.user_data['current_recommendation_index'] == 1