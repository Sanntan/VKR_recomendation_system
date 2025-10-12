from telegram import Update
from telegram.ext import ContextTypes
from .main_menu import show_main_menu

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /help."""
    help_text = (
        "📖 *Справочная информация*\n\n"
        "Доступные команды:\n"
        "• /start - Начать работу с ботом\n"
        "• /menu - Главное меню\n"
        "• /help - Справка\n"
        "• /cancel - Отмена текущего действия\n\n"
        "Основные функции:\n"
        "• 🎯 *Мои рекомендации* - персональные предложения мероприятий\n"
        "• 🔍 *Поиск мероприятий* - поиск по фильтрам\n"
        "• 📝 *Обратная связь* - ваши предложения и замечания\n\n"
        "Для начала работы введите /start"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /cancel."""
    await update.message.reply_text(
        "Текущее действие отменено. Для возврата в меню введите /menu",
        parse_mode='Markdown'
    )