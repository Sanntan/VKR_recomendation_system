"""
Тесты для логирования.
"""
import pytest
import logging
import sys
from pathlib import Path
from src.core.logging_config import (
    setup_logging,
    get_logger,
    StructuredFormatter,
    ColoredFormatter
)


class TestLogging:
    """Тесты для логирования."""
    
    def test_setup_logging(self):
        """Тест настройки логирования."""
        # Очищаем handlers перед тестом
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        setup_logging(level="DEBUG", service_name="test")
        
        # Проверяем, что у root логгера есть хотя бы один обработчик
        assert len(root_logger.handlers) > 0, "Handlers should be added to root logger"
        
        # Проверяем, что уровень root логгера установлен правильно
        assert root_logger.level == logging.DEBUG or root_logger.level == logging.NOTSET
        
        # Проверяем, что можем получить логгер
        logger = get_logger("test")
        assert logger is not None
        assert isinstance(logger, logging.Logger)
    
    def test_get_logger(self):
        """Тест получения логгера."""
        logger = get_logger("test_module")
        assert logger.name == "test_module"
        assert isinstance(logger, logging.Logger)
    
    def test_structured_formatter(self):
        """Тест структурированного форматтера."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        result = formatter.format(record)
        assert "timestamp" in result
        assert "level" in result
        assert "message" in result
    
    def test_colored_formatter(self):
        """Тест цветного форматтера."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        result = formatter.format(record)
        assert "Test message" in result

