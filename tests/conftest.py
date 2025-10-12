import pytest
import asyncio
from unittest.mock import patch

@pytest.fixture(autouse=True)
def mock_settings():
    """Автоматически мокаем настройки во всех тестах."""
    with patch('src.core.config.settings') as mock_settings:
        mock_settings.bot_token = "test_token_123"
        mock_settings.database_url = "sqlite+aiosqlite:///./test_test.db"
        mock_settings.log_level = "DEBUG"
        yield mock_settings

@pytest.fixture(scope="session")
def event_loop():
    """Фикстура для цикла событий."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()