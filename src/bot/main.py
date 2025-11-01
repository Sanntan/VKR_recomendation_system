import logging
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from telegram.request import BaseRequest
from src.core.config import settings
from src.bot.handlers.start import start_handler, handle_email_input
from src.bot.handlers.common import help_handler, cancel_handler
from src.bot.handlers.main_menu import main_menu_handler, show_main_menu, back_to_menu_handler
from src.bot.handlers.recommendations import show_recommendations, handle_recommendation_feedback, \
    show_next_recommendation
from src.bot.handlers.search import show_search_filters, handle_search_filter, show_next_search_result
from src.bot.handlers.feedback import request_feedback, receive_feedback, cancel_feedback, WAITING_FEEDBACK

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

    # ConversationHandler для обратной связи с per_message=True
    feedback_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(request_feedback, pattern="^feedback$")],
        states={
            WAITING_FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_feedback)]
        },
        fallbacks=[CallbackQueryHandler(cancel_feedback, pattern="^back_to_menu$")],
        per_message=True
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

    # Обработчик для сообщений с email (ожидаем его после команды /start)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email_input))

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
    application.run_polling(allowed_updates=Update.ALL_TYPES)  # Теперь Update импортирован


if __name__ == "__main__":
    main()