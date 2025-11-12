import logging
from typing import Optional
import traceback

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from telegram.request import BaseRequest
from telegram.error import TelegramError

from src.core.config import settings
from src.core.logging_config import setup_logging, get_logger
from src.core.sentry_config import init_sentry
from src.bot.middlewares.auth_middleware import AuthMiddleware
from src.bot.handlers.start import start_handler, handle_participant_id_input
from src.bot.handlers.common import help_handler, cancel_handler, unknown_command_handler
from src.bot.handlers.main_menu import main_menu_handler, show_main_menu, back_to_menu_handler
from src.bot.handlers.recommendations import show_recommendations, handle_recommendation_feedback, \
    show_next_recommendation, export_recommendations
from src.bot.handlers.search import show_search_filters, handle_search_filter, show_next_search_result
from src.bot.handlers.favorites import (
    show_personal_cabinet, show_favorites, handle_favorite_action, show_next_favorite
)
from src.bot.handlers.feedback import (
    request_feedback, handle_rating_selection, add_comment, send_feedback,
    receive_comment, cancel_feedback, WAITING_FEEDBACK_RATING, WAITING_FEEDBACK_COMMENT
)

# Настройка логирования
setup_logging(
    level=settings.log_level,
    service_name="vkr.bot"
)
logger = get_logger(__name__)

# Инициализация Sentry
init_sentry()


async def _log_error(update: object, context) -> None:  # type: ignore[no-untyped-def]
    """Улучшенный обработчик ошибок Telegram Application."""
    error = context.error
    error_type = type(error).__name__
    
    # Получаем информацию об обновлении
    update_info = {}
    if isinstance(update, Update):
        if update.message:
            update_info = {
                "message_id": update.message.message_id,
                "chat_id": update.message.chat.id,
                "user_id": update.message.from_user.id if update.message.from_user else None,
            }
        elif update.callback_query:
            update_info = {
                "callback_query_id": update.callback_query.id,
                "chat_id": update.callback_query.message.chat.id if update.callback_query.message else None,
                "user_id": update.callback_query.from_user.id if update.callback_query.from_user else None,
            }
    
    logger.error(
        f"Ошибка при обработке обновления: {error_type}: {str(error)}",
        extra={
            "error_type": error_type,
            "error_message": str(error),
            "update_info": update_info,
            "traceback": traceback.format_exc(),
        },
        exc_info=True
    )
    
    # Пытаемся уведомить пользователя об ошибке
    if isinstance(update, Update) and error and not isinstance(error, TelegramError):
        try:
            if update.message:
                await update.message.reply_text(
                    "❌ Произошла ошибка при обработке вашего запроса. "
                    "Попробуйте позже или используйте команду /menu для возврата в главное меню."
                )
            elif update.callback_query:
                await update.callback_query.answer(
                    "❌ Произошла ошибка. Попробуйте позже.",
                    show_alert=True
                )
        except Exception as notify_error:
            logger.warning(f"Не удалось уведомить пользователя об ошибке: {notify_error}")


def build_application(
    bot_token: Optional[str] = None,
    request: Optional[BaseRequest] = None,
) -> Application:
    """Создает и настраивает экземпляр ``Application`` с обработчиками бота."""

    token = bot_token or settings.bot_token
    if not token:
        raise ValueError("BOT_TOKEN не установлен")

    builder = Application.builder().token(token)
    if request is not None:
        builder.request(request)

    application = builder.build()

    # Создаем middleware для проверки авторизации
    auth_middleware = AuthMiddleware(allowed_commands=['start', 'help'])

    # ConversationHandler для обратной связи
    feedback_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(request_feedback, pattern="^feedback$")],
        states={
            WAITING_FEEDBACK_RATING: [
                CallbackQueryHandler(handle_rating_selection, pattern="^rating_"),
                CallbackQueryHandler(cancel_feedback, pattern="^back_to_menu$")
            ],
            WAITING_FEEDBACK_COMMENT: [
                CallbackQueryHandler(add_comment, pattern="^add_comment$"),
                CallbackQueryHandler(send_feedback, pattern="^send_without_comment$"),
                CallbackQueryHandler(cancel_feedback, pattern="^back_to_menu$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_comment)
            ]
        },
        fallbacks=[CallbackQueryHandler(cancel_feedback, pattern="^back_to_menu$")],
        per_message=False  # Изменено на False для корректной работы
    )

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("menu", main_menu_handler))
    application.add_handler(CommandHandler("cancel", cancel_handler))

    # Добавляем ConversationHandler для обратной связи (регистрируем раньше общих коллбеков)
    application.add_handler(feedback_conv_handler)

    # Обработчики callback queries для главного меню
    application.add_handler(CallbackQueryHandler(back_to_menu_handler, pattern="^back_to_menu$"))
    application.add_handler(CallbackQueryHandler(show_recommendations, pattern="^my_recommendations$"))
    application.add_handler(CallbackQueryHandler(export_recommendations, pattern="^export_recommendations$"))
    application.add_handler(CallbackQueryHandler(show_search_filters, pattern="^event_search$"))
    application.add_handler(CallbackQueryHandler(show_personal_cabinet, pattern="^personal_cabinet$"))

    # Обработчики для рекомендаций
    application.add_handler(CallbackQueryHandler(handle_recommendation_feedback, pattern="^(like|dislike)_"))
    application.add_handler(CallbackQueryHandler(show_next_recommendation, pattern="^show_other_events$"))

    # Обработчики для поиска
    application.add_handler(CallbackQueryHandler(handle_search_filter, pattern="^filter_"))
    application.add_handler(CallbackQueryHandler(show_next_search_result, pattern="^search_next$"))

    # Обработчики для избранного
    application.add_handler(CallbackQueryHandler(show_favorites, pattern="^my_favorites$"))
    application.add_handler(CallbackQueryHandler(handle_favorite_action, pattern="^(add_favorite|remove_favorite)_"))
    application.add_handler(CallbackQueryHandler(show_next_favorite, pattern="^favorite_next$"))

    # Обработчик для ввода participant_id (ожидаем его после команды /start)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_participant_id_input))

    # Обработчик неизвестных команд (должен быть последним)
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command_handler))

    application.add_error_handler(_log_error)

    return application


def main() -> None:
    """Запуск бота."""
    try:
        application = build_application()
    except ValueError:
        logger.error("BOT_TOKEN не установлен в переменных окружения!")
        return

    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
