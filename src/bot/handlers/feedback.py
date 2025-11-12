from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

from src.bot.middlewares.auth_middleware import auth_required
from src.bot.services.api_client import api_client, APIClientError

# Состояния для ConversationHandler
WAITING_FEEDBACK_RATING = 1
WAITING_FEEDBACK_COMMENT = 2

@auth_required
async def request_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает обратную связь от пользователя."""
    if update.callback_query:
        await update.callback_query.answer()

    context.user_data.pop('feedback_rating', None)

    keyboard = [
        [InlineKeyboardButton("⭐ 1", callback_data="rating_1")],
        [InlineKeyboardButton("⭐ 2", callback_data="rating_2")],
        [InlineKeyboardButton("⭐ 3", callback_data="rating_3")],
        [InlineKeyboardButton("⭐ 4", callback_data="rating_4")],
        [InlineKeyboardButton("⭐ 5", callback_data="rating_5")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "📝 *Обратная связь*\n\n"
        "Пожалуйста, оцените работу бота по шкале от 1 до 5 звезд:\n\n"
        "⭐ - Очень плохо\n"
        "⭐⭐ - Плохо\n"
        "⭐⭐⭐ - Нормально\n"
        "⭐⭐⭐⭐ - Хорошо\n"
        "⭐⭐⭐⭐⭐ - Отлично"
    )

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    return WAITING_FEEDBACK_RATING

@auth_required
async def handle_rating_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор рейтинга."""
    query = update.callback_query
    await query.answer()

    rating = int(query.data.split('_')[1])
    context.user_data['feedback_rating'] = rating

    keyboard = [
        [InlineKeyboardButton("💬 Добавить комментарий", callback_data="add_comment")],
        [InlineKeyboardButton("✅ Отправить без комментария", callback_data="send_without_comment")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    stars = "⭐" * rating
    text = (
        f"📝 *Обратная связь*\n\n"
        f"Вы выбрали оценку: {stars} ({rating}/5)\n\n"
        "Хотите добавить комментарий?"
    )

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    return WAITING_FEEDBACK_COMMENT

@auth_required
async def add_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает комментарий."""
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "💬 *Добавьте комментарий*\n\n"
        "Напишите ваш отзыв или предложения по улучшению:"
    )

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    return WAITING_FEEDBACK_COMMENT

@auth_required
async def send_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправляет обратную связь без комментария."""
    query = update.callback_query
    await query.answer()

    await save_feedback(update, context, comment=None)
    return ConversationHandler.END

@auth_required
async def receive_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает комментарий и сохраняет feedback."""
    comment = update.message.text
    await save_feedback(update, context, comment=comment)
    return ConversationHandler.END

async def save_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE, comment: str = None) -> None:
    """Сохраняет обратную связь в базу данных."""
    student = context.user_data.get('student')
    rating = context.user_data.get('feedback_rating')

    if not student or not rating:
        if update.message:
            await update.message.reply_text("❌ Ошибка сохранения отзыва.")
        return

    student_id = student.get("id") if isinstance(student, dict) else getattr(student, "id", None)
    if not student_id:
        if update.message:
            await update.message.reply_text("❌ Ошибка сохранения отзыва.")
        return

    try:
        await api_client.submit_feedback(student_id=student_id, rating=rating, comment=comment)
    except APIClientError:
        error_text = "❌ Не удалось сохранить отзыв. Попробуйте позже."
        if update.message:
            await update.message.reply_text(error_text)
        else:
            await update.callback_query.edit_message_text(
                error_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]])
            )
        return

    stars = "⭐" * rating
    text = (
        "✅ Спасибо за ваш отзыв!\n\n"
        f"Ваша оценка: {stars} ({rating}/5)\n"
        "Ваше мнение помогает нам становиться лучше! 💫"
    )

    keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    context.user_data.pop('feedback_rating', None)

@auth_required
async def cancel_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет процесс обратной связи."""
    await update.callback_query.answer()
    context.user_data.pop('feedback_rating', None)
    from .main_menu import show_main_menu
    await show_main_menu(update, context)
    return ConversationHandler.END