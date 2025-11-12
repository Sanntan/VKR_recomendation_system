"""
Конфигурация структурированного логирования для всего проекта.
"""
import logging
import sys
from pathlib import Path
from typing import Optional
import json
from datetime import datetime


class StructuredFormatter(logging.Formatter):
    """Форматтер для структурированного логирования в JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись лога в JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Добавляем исключение, если есть
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Добавляем дополнительные поля из extra
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
        
        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """Форматтер с цветами для консоли."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись с цветами."""
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    json_format: bool = False,
    service_name: str = "vkr"
) -> None:
    """
    Настраивает структурированное логирование для приложения.
    
    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Путь к файлу для записи логов (опционально)
        json_format: Использовать JSON формат для файлов
        service_name: Имя сервиса для логирования
    """
    # Удаляем все существующие обработчики
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Устанавливаем уровень
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    
    # Формат для консоли
    console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    console_formatter = ColoredFormatter(console_format) if sys.stdout.isatty() else logging.Formatter(console_format)
    
    # Обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Обработчик для файла, если указан
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        if json_format:
            file_formatter = StructuredFormatter()
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s"
            )
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Настраиваем логирование для внешних библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    logger = logging.getLogger(service_name)
    logger.info(f"Логирование настроено: уровень={level}, файл={log_file}, JSON={json_format}")


def get_logger(name: str) -> logging.Logger:
    """Получить логгер с указанным именем."""
    return logging.getLogger(name)

