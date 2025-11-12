import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, Message, User, Chat
from src.bot.handlers.start import start_handler, handle_participant_id_input, user_state
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
@patch('src.bot.handlers.start.api_client.get_bot_user', new_callable=AsyncMock)
async def test_start_handler(mock_get_bot_user, mock_update):
    """Тестирует обработчик команды /start."""
    # Возвращаем None вместо ошибки, чтобы пройти проверку и вызвать reply_html
    mock_get_bot_user.return_value = None
    mock_context = MagicMock()
    mock_context.user_data = {}

    await start_handler(mock_update, mock_context)

    # Проверяем, что был вызван reply_html
    mock_update.message.reply_html.assert_called_once()
    # Проверяем, что состояние пользователя установлено
    from src.bot.handlers.start import user_state
    assert user_state[123] == "awaiting_participant_id"


@pytest.mark.asyncio
@patch('src.bot.handlers.start.user_state', {123: "awaiting_participant_id"})
@patch('src.bot.handlers.start.show_main_menu', new_callable=AsyncMock)
async def test_handle_participant_id_input_valid(mock_show_menu, mock_update):
    """Тестирует обработку валидного participant_id."""
    # Устанавливаем валидный participant_id
    mock_update.message.text = "test_participant_001"
    mock_context = MagicMock()
    mock_context.user_data = {}

    with patch('src.bot.handlers.start.api_client.get_student_by_participant', new_callable=AsyncMock) as mock_get_student, \
         patch('src.bot.handlers.start.api_client.get_bot_user', new_callable=AsyncMock) as mock_get_bot_user, \
         patch('src.bot.handlers.start.api_client.create_bot_user', new_callable=AsyncMock) as mock_create_bot_user:
        mock_get_student.return_value = {"id": "test-id", "participant_id": "test_participant_001"}
        mock_get_bot_user.return_value = None  # No existing bot user
        mock_create_bot_user.return_value = None
        
        await handle_participant_id_input(mock_update, mock_context)

        # Проверяем, что было отправлено сообщение
        mock_update.message.reply_text.assert_called()
        
        # Проверяем, что показано главное меню
        mock_show_menu.assert_called_once_with(mock_update, mock_context)


@pytest.mark.asyncio
@patch('src.bot.handlers.start.user_state', {123: "awaiting_participant_id"})
async def test_handle_participant_id_input_invalid(mock_update):
    """Тестирует обработку невалидного participant_id."""
    mock_update.message.text = "invalid_id_that_fails_validation"
    mock_context = MagicMock()
    mock_context.user_data = {}

    with patch('src.bot.handlers.start.is_valid_participant_id', return_value=False):
        await handle_participant_id_input(mock_update, mock_context)

        # Проверяем, что было отправлено сообщение об ошибке
        mock_update.message.reply_text.assert_called()
        
        # Проверяем, что состояние пользователя НЕ сброшено
        from src.bot.handlers.start import user_state
        assert user_state[123] == "awaiting_participant_id"


@pytest.mark.asyncio
@patch('src.bot.handlers.start.user_state', {123: "awaiting_participant_id"})
@patch('src.bot.middlewares.auth_middleware.api_client.get_bot_user', new_callable=AsyncMock)
@patch('src.bot.middlewares.auth_middleware.api_client.update_bot_user_activity', new_callable=AsyncMock)
async def test_cancel_handler(mock_update_activity, mock_get_bot_user, mock_update):
    """Тестирует обработчик команды /cancel."""
    mock_get_bot_user.return_value = {"is_linked": True, "student": {"id": "test"}}
    mock_context = MagicMock()
    mock_context.user_data = {}

    await cancel_handler(mock_update, mock_context)

    # Проверяем, что отправлено сообщение
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "отменено" in call_args.lower()


@pytest.mark.asyncio
@patch('src.bot.handlers.start.user_state', {})
@patch('src.bot.middlewares.auth_middleware.api_client.get_bot_user', new_callable=AsyncMock)
@patch('src.bot.middlewares.auth_middleware.api_client.update_bot_user_activity', new_callable=AsyncMock)
async def test_cancel_handler_no_state(mock_update_activity, mock_get_bot_user, mock_update):
    """Тестирует /cancel когда нет активного состояния."""
    mock_get_bot_user.return_value = {"is_linked": True, "student": {"id": "test"}}
    mock_context = MagicMock()
    mock_context.user_data = {}

    await cancel_handler(mock_update, mock_context)

    # Проверяем, что отправлено соответствующее сообщение
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "отменено" in call_args.lower()


@pytest.mark.asyncio
async def test_help_handler(mock_update):
    """Тестирует обработчик команды /help."""
    mock_context = MagicMock()

    await help_handler(mock_update, mock_context)

    # Проверяем, что было отправлено справочное сообщение
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Справка" in call_args or "Доступные команды" in call_args