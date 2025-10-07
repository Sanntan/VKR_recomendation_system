import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from telegram.ext import Application
from src.core.config import Settings

@pytest.fixture
def settings():
    """Фикстура для настроек с тестовыми значениями."""
    return Settings(
        bot_token="test_token",
        database_url="sqlite+aiosqlite:///./test_test.db",
        log_level="DEBUG"
    )

@pytest.fixture
def mock_bot():
    """Фикстура для мока бота."""
    bot = MagicMock()
    bot.defaults = None
    return bot

@pytest.fixture
def mock_application(mock_bot):
    """Фикстура для мока Application."""
    application = MagicMock(spec=Application)
    application.bot = mock_bot
    return application

@pytest.fixture(scope="session")
def event_loop():
    """Фикстура для цикла событий."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()