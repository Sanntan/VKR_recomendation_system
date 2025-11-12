"""
Конфигурация Sentry для отслеживания ошибок.
"""
import logging
from typing import Optional
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from src.core.config import settings

logger = logging.getLogger(__name__)


def init_sentry(
    dsn: Optional[str] = None,
    environment: Optional[str] = None,
    traces_sample_rate: Optional[float] = None,
    profiles_sample_rate: Optional[float] = None,
) -> None:
    """
    Инициализирует Sentry для отслеживания ошибок.
    
    Args:
        dsn: Sentry DSN (если None, берется из settings)
        environment: Окружение (development, production, staging)
        traces_sample_rate: Процент запросов для трейсинга (0.0 - 1.0)
        profiles_sample_rate: Процент запросов для профилирования (0.0 - 1.0)
    """
    dsn = dsn or settings.sentry_dsn
    if not dsn:
        logger.info("Sentry DSN не указан, отслеживание ошибок отключено")
        return
    
    environment = environment or settings.sentry_environment
    traces_sample_rate = traces_sample_rate if traces_sample_rate is not None else settings.sentry_traces_sample_rate
    profiles_sample_rate = profiles_sample_rate if profiles_sample_rate is not None else settings.sentry_profiles_sample_rate
    
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
            LoggingIntegration(
                level=logging.INFO,  # Логировать INFO и выше
                event_level=logging.ERROR  # Отправлять в Sentry только ERROR и выше
            ),
        ],
        # Настройки для фильтрации чувствительных данных
        before_send=lambda event, hint: event,  # Можно добавить фильтрацию
        # Включаем локальные переменные в стек трейсы (осторожно в production!)
        attach_stacktrace=True,
        # Отправляем только в production/staging
        send_default_pii=False,  # Не отправлять персональные данные по умолчанию
    )
    
    logger.info(f"Sentry инициализирован: environment={environment}, traces_sample_rate={traces_sample_rate}")


def capture_exception(error: Exception, **kwargs) -> None:
    """Захватывает исключение и отправляет в Sentry."""
    sentry_sdk.capture_exception(error, **kwargs)


def capture_message(message: str, level: str = "info", **kwargs) -> None:
    """Захватывает сообщение и отправляет в Sentry."""
    sentry_sdk.capture_message(message, level=level, **kwargs)

