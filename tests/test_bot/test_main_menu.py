import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from src.bot.handlers.main_menu import show_main_menu, main_menu_handler


@pytest.fixture
def mock_update_with_callback():
    """Создает мок Update с callback_query."""
    update = MagicMock(spec=Update)
    update.callback_query = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.message = None
    return update


@pytest.fixture
def mock_update_with_message():
    """Создает мок Update с message."""
    update = MagicMock(spec=Update)
    update.callback_query = None
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_show_main_menu_with_callback(mock_update_with_callback):
    """Тестирует показ главного меню через callback."""
    mock_context = AsyncMock()

    await show_main_menu(mock_update_with_callback, mock_context)

    # Проверяем, что был вызван edit_message_text
    mock_update_with_callback.callback_query.edit_message_text.assert_called_once()

    # Проверяем содержимое сообщения - исправленный способ получения аргументов
    call_args = mock_update_with_callback.callback_query.edit_message_text.call_args
    # Аргументы могут передаваться как позиционные или именованные
    if call_args[0]:  # Если есть позиционные аргументы
        text = call_args[0][0]  # Первый позиционный аргумент
    else:
        text = call_args[1]['text']  # Именованный аргумент

    assert "Главное меню" in text
    assert "Мои рекомендации" in text


@pytest.mark.asyncio
async def test_show_main_menu_with_message(mock_update_with_message):
    """Тестирует показ главного меню через сообщение."""
    mock_context = AsyncMock()

    await show_main_menu(mock_update_with_message, mock_context)

    # Проверяем, что был вызван reply_text
    mock_update_with_message.message.reply_text.assert_called_once()

    # Проверяем содержимое сообщения
    call_args = mock_update_with_message.message.reply_text.call_args
    text = call_args[0][0]  # text передается как positional argument
    assert "Главное меню" in text


@pytest.mark.asyncio
async def test_main_menu_handler(mock_update_with_message):
    """Тестирует обработчик команды /menu."""
    mock_context = AsyncMock()

    await main_menu_handler(mock_update_with_message, mock_context)

    # Проверяем, что был вызван reply_text
    mock_update_with_message.message.reply_text.assert_called_once()