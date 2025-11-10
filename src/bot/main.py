import logging
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from telegram.request import BaseRequest
from src.core.config import settings
from src.bot.middlewares.auth_middleware import AuthMiddleware
from src.bot.handlers.start import start_handler, handle_participant_id_input
from src.bot.handlers.common import help_handler, cancel_handler, unknown_command_handler
from src.bot.handlers.main_menu import main_menu_handler, show_main_menu, back_to_menu_handler
from src.bot.handlers.recommendations import show_recommendations, handle_recommendation_feedback, \
    show_next_recommendation
from src.bot.handlers.search import show_search_filters, handle_search_filter, show_next_search_result
from src.bot.handlers.feedback import (
    request_feedback, handle_rating_selection, add_comment, send_feedback,
    receive_comment, cancel_feedback, WAITING_FEEDBACK_RATING, WAITING_FEEDBACK_COMMENT
)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, settings.log_level.upper())
)
logger = logging.getLogger(__name__)


async def _log_error(update: object, context) -> None:  # type: ignore[no-untyped-def]
    """Стандартный обработчик ошибок Telegram Application."""
    logger.error("Ошибка при обработке обновления %s: %s", update, context.error)


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

    # Обработчики callback queries для главного меню
    application.add_handler(CallbackQueryHandler(back_to_menu_handler, pattern="^back_to_menu$"))
    application.add_handler(CallbackQueryHandler(show_recommendations, pattern="^my_recommendations$"))
    application.add_handler(CallbackQueryHandler(show_search_filters, pattern="^event_search$"))

    # Обработчики для рекомендаций
    application.add_handler(CallbackQueryHandler(handle_recommendation_feedback, pattern="^(like|dislike)_"))
    application.add_handler(CallbackQueryHandler(show_next_recommendation, pattern="^show_other_events$"))

    # Обработчики для поиска
    application.add_handler(CallbackQueryHandler(handle_search_filter, pattern="^filter_"))
    application.add_handler(CallbackQueryHandler(show_next_search_result, pattern="^search_next$"))

    # Добавляем ConversationHandler для обратной связи
    application.add_handler(feedback_conv_handler)

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
