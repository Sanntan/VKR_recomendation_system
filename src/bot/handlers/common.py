from telegram import Update
from telegram.ext import ContextTypes
from src.bot.middlewares.auth_middleware import allow_unauthorized, auth_required

@allow_unauthorized
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /help."""
    help_text = (
        "🆘 *Справка по боту*\n\n"
        "Этот бот помогает студентам ТюмГУ находить подходящие мероприятия.\n\n"
        "*Доступные команды:*\n"
        "• /start - Авторизация в системе\n"
        "• /help - Эта справка\n"
        "• /menu - Главное меню\n"
        "• /cancel - Отмена текущего действия\n\n"
        "*После авторизации доступны:*\n"
        "• 🎯 Мои рекомендации - персональные предложения\n"
        "• 🔍 Поиск мероприятий - фильтры и поиск\n"
        "• 📝 Обратная связь - ваши предложения"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

@auth_required
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /cancel."""
    await update.message.reply_text("Действие отменено.")

@allow_unauthorized
async def unknown_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает неизвестные команды."""
    await update.message.reply_text(
        "❓ Неизвестная команда.\n\n"
        "Используйте /menu для просмотра доступных функций или /help для справки."
    )