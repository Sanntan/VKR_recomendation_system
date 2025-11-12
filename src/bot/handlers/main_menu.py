from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from src.bot.middlewares.auth_middleware import auth_required

@auth_required
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает главное меню с основными функциями."""
    keyboard = [
        [InlineKeyboardButton("🎯 Мои рекомендации", callback_data="my_recommendations")],
        [InlineKeyboardButton("📥 Выгрузить рекомендации", callback_data="export_recommendations")],
        [InlineKeyboardButton("🔍 Поиск мероприятий", callback_data="event_search")],
        [InlineKeyboardButton("📝 Обратная связь", callback_data="feedback")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "🏠 *Главное меню*\n\n"
        "Выберите нужный раздел:\n"
        "• 🎯 *Мои рекомендации* - персональные предложения мероприятий\n"
        "• 📥 *Выгрузить рекомендации* - скачать все рекомендации в формате DOCX\n"
        "• 🔍 *Поиск мероприятий* - поиск по различным критериям\n"
        "• 📝 *Обратная связь* - оценка работы бота (1-5 звезд)"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        # Обрабатываем как обычное сообщение, так и отредактированное
        message = update.message or update.edited_message
        if message:
            await message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

@auth_required
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /menu."""
    await show_main_menu(update, context)

@auth_required
async def back_to_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки 'Назад' в главное меню."""
    await show_main_menu(update, context)