from typing import Any, Coroutine

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

# Состояния для ConversationHandler
WAITING_FEEDBACK = 1


async def request_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает обратную связь от пользователя."""
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "📝 *Обратная связь*\n\n"
        "Пожалуйста, напишите ваши предложения, замечания или идеи по улучшению системы.\n\n"
        "Мы ценим каждое ваше сообщение! ✨"
    )

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    return WAITING_FEEDBACK


async def receive_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает и обрабатывает обратную связь."""
    feedback_text = update.message.text
    user = update.effective_user

    # Здесь можно сохранить feedback в базу данных или отправить администратору
    print(f"Feedback from {user.full_name} (@{user.username}): {feedback_text}")

    # Показываем подтверждение
    keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "✅ Спасибо за ваш отзыв! Мы обязательно его рассмотрим.\n\n"
        "Ваше мнение помогает нам становиться лучше! 💫",
        reply_markup=reply_markup
    )

    return ConversationHandler.END


async def cancel_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет процесс обратной связи."""
    await update.callback_query.answer()
    from .main_menu import show_main_menu
    await show_main_menu(update, context)
    return ConversationHandler.END