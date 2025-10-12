from telegram import Update
from telegram.ext import ContextTypes
from src.bot.services.validation import is_valid_utmn_email
from .main_menu import show_main_menu

# Временное хранилище состояния
user_state = {}


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /start."""
    user = update.effective_user
    user_id = user.id

    # Формируем имя для приветствия
    user_name = user.first_name or user.username or "Студент"

    # Приветственное сообщение
    welcome_text = (
        f"Здравствуйте, {user_name}!\n\n"
        "Добро пожаловать в систему рекомендации мероприятий ТюмГУ.\n"
        "Для получения персональных рекомендаций нам необходимо идентифицировать вас в системе.\n\n"
        "Пожалуйста, введите вашу **корпоративную почту** в формате:\n"
        "`stud0000######@study.utmn.ru`"
    )
    await update.message.reply_html(welcome_text)

    # Устанавливаем состояние пользователя "ожидаем email"
    user_state[user_id] = "awaiting_email"


async def handle_email_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ввод email пользователем."""
    user_id = update.effective_user.id
    user_input = update.message.text.strip()

    # Проверяем, ожидаем ли мы email от этого пользователя
    if user_state.get(user_id) != "awaiting_email":
        # Если нет, показываем главное меню
        await show_main_menu(update, context)
        return

    # Валидируем email
    if is_valid_utmn_email(user_input):
        # Email корректен
        success_text = (
            "✅ Спасибо! Ваш email принят и верифицирован.\n\n"
            "Теперь вы можете пользоваться всеми функциями бота!"
        )
        await update.message.reply_text(success_text)

        # Сбрасываем состояние пользователя
        user_state.pop(user_id, None)

        # Показываем главное меню
        await show_main_menu(update, context)

    else:
        # Email некорректен
        error_text = (
            "❌ Введенный email не соответствует корпоративному формату ТюмГУ.\n\n"
            "Пожалуйста, введите email в формате:\n"
            "`stud0000######@study.utmn.ru`\n\n"
            "Убедитесь, что вы вводите его правильно."
        )
        await update.message.reply_html(error_text)