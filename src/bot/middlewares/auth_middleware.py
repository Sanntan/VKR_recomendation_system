from telegram import Update
from telegram.ext import ContextTypes, CallbackContext
from functools import wraps
from typing import Any, Optional
import logging
from src.core.database.connection import get_db
from src.core.database.crud.bot_users import get_bot_user_with_student

logger = logging.getLogger(__name__)


# Декораторы для обработчиков
def auth_required(func):
    """Декоратор для проверки авторизации пользователя."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return await func(update, context, *args, **kwargs)

        user_id = update.effective_user.id

        # Проверяем авторизацию пользователя
        db = get_db()
        try:
            bot_user = get_bot_user_with_student(db, user_id)
            if not bot_user or not bot_user.is_linked:
                if update.message:
                    await update.message.reply_text(
                        "❌ Вы не авторизованы!\n\n"
                        "Используйте команду /start для авторизации."
                    )
                return

            # Обновляем время активности
            from src.core.database.crud.bot_users import update_bot_user_activity
            update_bot_user_activity(db, user_id)

            # Сохраняем информацию о студенте в контексте
            context.user_data['student'] = bot_user.student

        finally:
            db.close()

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
        from src.core.database.connection import get_db
        from src.core.database.crud.bot_users import get_bot_user_with_student

        if not update.effective_user:
            return False

        user_id = update.effective_user.id

        db = get_db()
        try:
            bot_user = get_bot_user_with_student(db, user_id)
            if not bot_user or not bot_user.is_linked:
                return False

            # Обновляем время активности
            from src.core.database.crud.bot_users import update_bot_user_activity
            update_bot_user_activity(db, user_id)

            # Сохраняем информацию о студенте в контексте
            context.user_data['student'] = bot_user.student
            return True

        except Exception as e:
            logger.error(f"Ошибка при проверке авторизации: {e}")
            return False
        finally:
            db.close()