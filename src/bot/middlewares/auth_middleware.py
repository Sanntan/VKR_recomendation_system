from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes, CallbackContext
from functools import wraps
from typing import Any, Optional
import logging
from src.bot.services.api_client import api_client, APIClientError

logger = logging.getLogger(__name__)

BOT_USER_CACHE_TTL = timedelta(seconds=30)
ACTIVITY_THROTTLE = timedelta(seconds=60)


def _get_cached_bot_user(context: ContextTypes.DEFAULT_TYPE, now: datetime) -> Optional[dict]:
    cache_entry = context.user_data.get('_bot_user_cache')
    if cache_entry:
        timestamp = cache_entry.get('timestamp')
        if isinstance(timestamp, datetime) and now - timestamp < BOT_USER_CACHE_TTL:
            return cache_entry.get('data')
    return None


def _store_bot_user_cache(context: ContextTypes.DEFAULT_TYPE, bot_user: dict, now: datetime) -> None:
    context.user_data['_bot_user_cache'] = {'data': bot_user, 'timestamp': now}
    context.user_data['bot_user'] = bot_user
    context.user_data['student'] = bot_user.get("student")


def _should_ping_activity(context: ContextTypes.DEFAULT_TYPE, now: datetime) -> bool:
    last_ping = context.user_data.get('_last_activity_ping')
    if isinstance(last_ping, datetime) and now - last_ping < ACTIVITY_THROTTLE:
        return False
    context.user_data['_last_activity_ping'] = now
    return True


# Декораторы для обработчиков
def auth_required(func):
    """Декоратор для проверки авторизации пользователя."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return await func(update, context, *args, **kwargs)

        user_id = update.effective_user.id
        now = datetime.utcnow()

        bot_user = _get_cached_bot_user(context, now)
        if bot_user:
            context.user_data['bot_user'] = bot_user
            context.user_data['student'] = bot_user.get("student")
        else:
            try:
                bot_user = await api_client.get_bot_user(user_id)
            except APIClientError as exc:
                logger.error("Не удалось получить данные пользователя из API: %s", exc)
                if update.message:
                    await update.message.reply_text(
                        "❌ Внутренняя ошибка сервера. Попробуйте позже."
                    )
                return

            if not bot_user or not bot_user.get("is_linked"):
                if update.message:
                    await update.message.reply_text(
                        "❌ Вы не авторизованы!\n\n"
                        "Используйте команду /start для авторизации."
                    )
                return

            _store_bot_user_cache(context, bot_user, now)
        if bot_user:
            context.user_data['bot_user'] = bot_user
            context.user_data['student'] = bot_user.get("student")

        if _should_ping_activity(context, now):
            try:
                await api_client.update_bot_user_activity(user_id)
            except APIClientError as exc:
                logger.warning("Не удалось обновить активность пользователя: %s", exc)

        return await func(update, context, *args, **kwargs)

    return wrapper


def allow_unauthorized(func):
    """Декоратор для функций, доступных без авторизации."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        return await func(update, context, *args, **kwargs)

    return wrapper


# Middleware класс для применения в Application
class AuthMiddleware:
    """Middleware для проверки авторизации пользователя."""

    def __init__(self, allowed_commands: list = None):
        self.allowed_commands = allowed_commands or ['start', 'help', 'cancel']

    async def __call__(self, update: Update, context: CallbackContext, next_handler: Any) -> Any:
        # Пропускаем проверку для разрешенных команд
        if update.message and update.message.text:
            command = update.message.text.split()[0].lstrip('/')
            if command in self.allowed_commands:
                return await next_handler(update, context)

        # Проверка авторизации для других команд
        if not await self.is_authenticated(update, context):
            if update.message:
                await update.message.reply_text(
                    "❌ Вы не авторизованы!\n\n"
                    "Используйте команду /start для авторизации."
                )
            return

        return await next_handler(update, context)

    async def is_authenticated(self, update: Update, context: CallbackContext) -> bool:
        """Проверяет, авторизован ли пользователь."""
        if not update.effective_user:
            return False

        user_id = update.effective_user.id

        now = datetime.utcnow()
        bot_user = _get_cached_bot_user(context, now)
        if bot_user:
            context.user_data['bot_user'] = bot_user
            context.user_data['student'] = bot_user.get("student")
        else:
            try:
                bot_user = await api_client.get_bot_user(user_id)
            except APIClientError as exc:
                logger.error("Ошибка при проверке авторизации: %s", exc)
                return False

            if not bot_user or not bot_user.get("is_linked"):
                return False

            _store_bot_user_cache(context, bot_user, now)
        if bot_user:
            context.user_data['bot_user'] = bot_user
            context.user_data['student'] = bot_user.get("student")

        if _should_ping_activity(context, now):
            try:
                await api_client.update_bot_user_activity(user_id)
            except APIClientError as exc:
                logger.warning("Не удалось обновить активность пользователя: %s", exc)

        return True