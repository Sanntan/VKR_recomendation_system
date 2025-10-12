import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, InlineKeyboardMarkup
from src.bot.handlers.recommendations import show_recommendations, handle_recommendation_feedback, \
    show_next_recommendation
from datetime import datetime, timedelta


@pytest.fixture
def mock_update_with_callback():
    """Создает мок Update с callback_query."""
    update = MagicMock(spec=Update)
    update.callback_query = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.answer = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_show_recommendations(mock_update_with_callback):
    """Тестирует показ рекомендаций."""
    mock_context = MagicMock()
    mock_context.user_data = {}

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
async def test_handle_recommendation_feedback_like(mock_update_with_callback):
    """Тестирует обработку лайка рекомендации."""
    mock_context = MagicMock()
    mock_context.user_data = {}

    mock_update_with_callback.callback_query.data = "like_1"

    await handle_recommendation_feedback(mock_update_with_callback, mock_context)

    # Проверяем, что answer был вызван с правильным сообщением
    mock_update_with_callback.callback_query.answer.assert_called_with("Спасибо! Учтем ваши предпочтения 👍")

    # Проверяем, что лайк сохранился
    assert mock_context.user_data['liked_events'] == [1]


@pytest.mark.asyncio
async def test_handle_recommendation_feedback_dislike(mock_update_with_callback):
    """Тестирует обработку дизлайка рекомендации."""
    mock_context = MagicMock()
    mock_context.user_data = {}

    mock_update_with_callback.callback_query.data = "dislike_1"

    await handle_recommendation_feedback(mock_update_with_callback, mock_context)

    # Проверяем, что answer был вызван с правильным сообщением
    mock_update_with_callback.callback_query.answer.assert_called_with("Понятно, учтем ваши предпочтения 👎")

    # Проверяем, что дизлайк сохранился
    assert mock_context.user_data['disliked_events'] == [1]


@pytest.mark.asyncio
async def test_show_next_recommendation(mock_update_with_callback):
    """Тестирует показ следующей рекомендации."""
    mock_context = MagicMock()

    # Используем полные тестовые данные как в реальном коде
    mock_context.user_data = {
        'current_recommendations': [
            {
                'id': 1,
                'title': 'Event 1',
                'date': (datetime.now() + timedelta(days=5)).strftime('%d %B'),
                'format': 'офлайн (Центр компетенций, ауд. 202)',
                'skills': 'коммуникативность, ориентация на результат',
                'registration_link': 'https://example.com/event1'
            },
            {
                'id': 2,
                'title': 'Event 2',
                'date': (datetime.now() + timedelta(days=3)).strftime('%d %B'),
                'format': 'онлайн (Zoom)',
                'skills': 'программирование, аналитическое мышление',
                'registration_link': 'https://example.com/event2'
            }
        ],
        'current_recommendation_index': 0
    }

    await show_next_recommendation(mock_update_with_callback, mock_context)

    # Проверяем, что был вызван edit_message_text
    assert mock_update_with_callback.callback_query.edit_message_text.called

    # Проверяем, что индекс обновился
    assert mock_context.user_data['current_recommendation_index'] == 1