import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from src.core.config import settings
from src.bot.handlers.start import start_handler, handle_email_input
from src.bot.handlers.common import help_handler, cancel_handler

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=settings.log_level
)
logger = logging.getLogger(__name__)

def main() -> None:
    """Запуск бота."""
    # Создаем Application и передаем ему токен бота.
    application = Application.builder().token(settings.bot_token).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("cancel", cancel_handler))

    # Обработчик для сообщений с email (ожидаем его после команды /start)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email_input))

    # Запускаем бота до тех пор, пока пользователь не остановит его (Ctrl+C)
    application.run_polling(allowed_updates=[])

if __name__ == "__main__":
    main()