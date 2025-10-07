import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, Message, User, Chat
from src.bot.handlers.start import start_handler, handle_email_input, user_state
from src.bot.handlers.common import cancel_handler


@pytest.fixture
def mock_update():
    """Создает мок объекта Update."""
    user = User(
        id=123,
        first_name="Test",
        last_name="User",
        is_bot=False,
        username="test_user"
    )
    chat = Chat(id=1, type="private")

    # Создаем мок сообщения с установленным текстом
    message = MagicMock(spec=Message)
    message.message_id = 1
    message.date = None
    message.chat = chat
    message.from_user = user
    message.text = ""  # Устанавливаем текст по умолчанию
    message.reply_html = AsyncMock()
    message.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.update_id = 1
    update.message = message
    update.effective_user = user

    return update


@pytest.mark.asyncio
async def test_start_handler(mock_update):
    """Тестирует обработчик команды /start."""
    mock_context = AsyncMock()

    await start_handler(mock_update, mock_context)

    # Проверяем, что был вызван reply_html
    mock_update.message.reply_html.assert_called_once()
    # Проверяем, что состояние пользователя установлено
    assert user_state[123] == "awaiting_email"


@pytest.mark.asyncio
async def test_handle_email_input_valid(mock_update):
    """Тестирует обработку валидного email."""
    # Устанавливаем состояние "ожидаем email"
    user_state[123] = "awaiting_email"
    # Устанавливаем валидный email
    mock_update.message.text = "stud0000123456@study.utmn.ru"
    mock_context = AsyncMock()

    await handle_email_input(mock_update, mock_context)

    # Проверяем, что было отправлено сообщение об успехе
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Спасибо! Ваш email принят." in call_args
    # Проверяем, что состояние пользователя сброшено
    assert 123 not in user_state


@pytest.mark.asyncio
async def test_handle_email_input_invalid(mock_update):
    """Тестирует обработку невалидного email."""
    user_state[123] = "awaiting_email"
    mock_update.message.text = "invalid_email@example.com"
    mock_context = AsyncMock()

    await handle_email_input(mock_update, mock_context)

    # Проверяем, что было отправлено сообщение об ошибке
    mock_update.message.reply_html.assert_called_once()
    error_message = mock_update.message.reply_html.call_args[0][0]
    assert "не соответствует" in error_message or "формату" in error_message
    # Проверяем, что состояние пользователя НЕ сброшено
    assert user_state[123] == "awaiting_email"


@pytest.mark.asyncio
async def test_cancel_handler(mock_update):
    """Тестирует обработчик команды /cancel."""
    # Устанавливаем состояние
    user_state[123] = "awaiting_email"
    mock_context = AsyncMock()

    await cancel_handler(mock_update, mock_context)

    # Проверяем, что состояние сброшено и отправлено сообщение
    mock_update.message.reply_text.assert_called_once()
    assert 123 not in user_state


@pytest.mark.asyncio
async def test_cancel_handler_no_state(mock_update):
    """Тестирует /cancel когда нет активного состояния."""
    # Убедимся, что состояния нет
    user_state.pop(123, None)
    mock_context = AsyncMock()

    await cancel_handler(mock_update, mock_context)

    # Проверяем, что отправлено соответствующее сообщение
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Нечего отменять" in call_args