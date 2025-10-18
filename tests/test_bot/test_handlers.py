import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, Message, User, Chat
from src.bot.handlers.start import start_handler, handle_email_input, user_state
from src.bot.handlers.common import help_handler, cancel_handler


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
    update.callback_query = None  # Добавляем callback_query

    return update


@pytest.mark.asyncio
@patch('src.bot.handlers.start.user_state', {})
async def test_start_handler(mock_update):
    """Тестирует обработчик команды /start."""
    mock_context = AsyncMock()

    await start_handler(mock_update, mock_context)

    # Проверяем, что был вызван reply_html
    mock_update.message.reply_html.assert_called_once()
    # Проверяем, что состояние пользователя установлено
    from src.bot.handlers.start import user_state
    assert user_state[123] == "awaiting_email"


@pytest.mark.asyncio
@patch('src.bot.handlers.start.user_state', {123: "awaiting_email"})
@patch('src.bot.handlers.start.show_main_menu')
async def test_handle_email_input_valid(mock_show_menu, mock_update):
    """Тестирует обработку валидного email."""
    # Устанавливаем валидный email
    mock_update.message.text = "stud0000123456@study.utmn.ru"
    mock_context = AsyncMock()

    await handle_email_input(mock_update, mock_context)

    # Проверяем, что было отправлено сообщение об успехе
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Спасибо! Ваш email принят" in call_args

    # Проверяем, что состояние пользователя сброшено
    from src.bot.handlers.start import user_state
    assert 123 not in user_state

    # Проверяем, что показано главное меню
    mock_show_menu.assert_called_once_with(mock_update, mock_context)


@pytest.mark.asyncio
@patch('src.bot.handlers.start.user_state', {123: "awaiting_email"})
async def test_handle_email_input_invalid(mock_update):
    """Тестирует обработку невалидного email."""
    mock_update.message.text = "invalid_email@example.com"
    mock_context = AsyncMock()

    await handle_email_input(mock_update, mock_context)

    # Проверяем, что было отправлено сообщение об ошибке через reply_text
    mock_update.message.reply_text.assert_called_once()

    # Получаем текст сообщения об ошибке
    call_args = mock_update.message.reply_text.call_args[0][0]

    # Проверяем содержание сообщения об ошибке
    assert "не соответствует" in call_args or "формату" in call_args

    # Проверяем, что состояние пользователя НЕ сброшено
    from src.bot.handlers.start import user_state
    assert user_state[123] == "awaiting_email"


@pytest.mark.asyncio
@patch('src.bot.handlers.start.user_state', {123: "awaiting_email"})
async def test_cancel_handler(mock_update):
    """Тестирует обработчик команды /cancel."""
    mock_context = AsyncMock()

    await cancel_handler(mock_update, mock_context)

    # Проверяем, что отправлено сообщение
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "отменено" in call_args.lower()
    # Проверяем, что состояние НЕ сброшено (теперь cancel не сбрасывает состояния)
    from src.bot.handlers.start import user_state
    assert 123 in user_state  # Состояние остается


@pytest.mark.asyncio
@patch('src.bot.handlers.start.user_state', {})
async def test_cancel_handler_no_state(mock_update):
    """Тестирует /cancel когда нет активного состояния."""
    mock_context = AsyncMock()

    await cancel_handler(mock_update, mock_context)

    # Проверяем, что отправлено соответствующее сообщение
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "отменено" in call_args.lower()  # Новый текст сообщения


@pytest.mark.asyncio
async def test_help_handler(mock_update):
    """Тестирует обработчик команды /help."""
    mock_context = AsyncMock()

    await help_handler(mock_update, mock_context)

    # Проверяем, что было отправлено справочное сообщение
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Справочная информация" in call_args or "Доступные команды" in call_args