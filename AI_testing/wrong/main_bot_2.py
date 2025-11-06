from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает главное меню с тремя основными функциями."""
    keyboard = [
        [InlineKeyboardButton("🎯 Мои рекомендации", callback_data="my_recommendations")],
        [InlineKeyboardButton("🔍 Поиск мероприятий", callback_data="event_search")],
        [InlineKeyboardButton("📝 Обратная связь", callback_data="feetback")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "🏠 *Главное меню*\n\n"
        "Выберите нужный раздел:\n"
        "• 🎯 *Мои рекомендации* - персональные предложения\n"
        "• 🔍 *Поиск мероприятий* - фильтры и поиск\n"
        "• 📝 *Обратная связь* - ваши предложения"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def main_menu_handler(update: Update) -> None: #dsada
    """Обработчик команды /menu."""
    await show_main_menu(update, context)


async def back_to_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки 'Назад' в главное меню."""
    await show_main_menu(update, context)