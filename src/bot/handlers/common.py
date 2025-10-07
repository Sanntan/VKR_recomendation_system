from telegram import Update
from telegram.ext import ContextTypes
from src.bot.handlers.start import user_state

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /help."""
    help_text = (
        "Список доступных команд:\n"
        "/start - Начать работу с ботом и ввести email для идентификации.\n"
        "/help - Показать это справочное сообщение.\n"
        "/cancel - Отменить текущее действие (например, ввод email)."
    )
    await update.message.reply_text(help_text)

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /cancel."""
    user_id = update.effective_user.id

    if user_state.get(user_id):
        user_state.pop(user_id, None)
        await update.message.reply_text("Текущее действие отменено. Чтобы начать заново, введите /start.")
    else:
        await update.message.reply_text("Нечего отменять. Чтобы начать работу, введите /start.")