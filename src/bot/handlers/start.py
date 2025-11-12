from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from src.bot.services.validation import is_valid_participant_id
from src.bot.middlewares.auth_middleware import allow_unauthorized
from .main_menu import show_main_menu
from src.bot.services.api_client import api_client, APIClientError

# Временное хранилище состояния
user_state = {}

@allow_unauthorized
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /start."""
    user = update.effective_user
    user_id = user.id

    try:
        bot_user = await api_client.get_bot_user(user_id)
        if bot_user and bot_user.get("is_linked"):
            context.user_data['_bot_user_cache'] = {'data': bot_user, 'timestamp': datetime.utcnow()}
            context.user_data['bot_user'] = bot_user
            context.user_data['student'] = bot_user.get("student")
            await show_main_menu(update, context)
            return
    except APIClientError:
        await update.message.reply_text(
            "❌ Не удалось проверить авторизацию. Попробуйте позже."
        )
        return

    # Формируем имя для приветствия
    user_name = user.first_name or user.username or "Студент"

    # Приветственное сообщение с HTML-разметкой
    welcome_text = (
        f"Здравствуйте, {user_name}!\n\n"
        "<b>Добро пожаловать в систему рекомендации мероприятий ТюмГУ.</b>\n"
        "Для получения персональных рекомендаций нам необходимо идентифицировать вас в системе.\n\n"
        "Пожалуйста, введите ваш <b>participant_id</b> (идентификатор участника):"
    )

    await update.message.reply_html(welcome_text)

    # Устанавливаем состояние пользователя "ожидаем participant_id"
    user_state[user_id] = "awaiting_participant_id"

@allow_unauthorized
async def handle_participant_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ввод participant_id пользователем."""
    # Проверяем, что сообщение существует и содержит текст
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    user_input = update.message.text.strip()

    # Проверяем, ожидаем ли мы participant_id от этого пользователя
    if user_state.get(user_id) != "awaiting_participant_id":
        # Если нет, проверяем авторизацию
        try:
            bot_user = await api_client.get_bot_user(user_id)
        except APIClientError:
            await update.message.reply_text(
                "❌ Не удалось проверить авторизацию. Попробуйте позже."
            )
            return

        if bot_user and bot_user.get("is_linked"):
            context.user_data['_bot_user_cache'] = {'data': bot_user, 'timestamp': datetime.utcnow()}
            context.user_data['bot_user'] = bot_user
            context.user_data['student'] = bot_user.get("student")
            await show_main_menu(update, context)
        else:
            await update.message.reply_text(
                "❌ Вы не авторизованы!\n\n"
                "Используйте команду /start для авторизации."
            )
        return

    # Валидируем participant_id
    if is_valid_participant_id(user_input):
        # Проверяем, существует ли такой студент в базе
        try:
            student = await api_client.get_student_by_participant(user_input)
        except APIClientError:
            await update.message.reply_text(
                "❌ Не удалось проверить participant_id. Попробуйте позже."
            )
            return

        if not student:
            error_text = (
                "❌ Студент с таким participant_id не найден в системе.\n\n"
                "Пожалуйста, проверьте правильность ввода и попробуйте еще раз.\n"
                "Если проблема persists, обратитесь к администратору."
            )
            await update.message.reply_text(error_text)
            return

        try:
            existing_bot_user = await api_client.get_bot_user(user_id)
        except APIClientError:
            existing_bot_user = None

        if existing_bot_user and existing_bot_user.get("student", {}).get("id") == student["id"]:
            success_text = (
                "✅ Вы уже авторизованы в системе!\n\n"
                "Теперь вы можете пользоваться всеми функциями бота!"
            )
            await update.message.reply_text(success_text)
        elif existing_bot_user and existing_bot_user.get("is_linked"):
            error_text = (
                "❌ Этот Telegram аккаунт уже привязан к другому студенту.\n\n"
                "Если это ошибка, обратитесь к администратору."
            )
            await update.message.reply_text(error_text)
            return
        else:
            try:
                await api_client.create_bot_user(
                    telegram_id=user_id,
                    student_id=student["id"],
                    username=update.effective_user.username,
                )
            except APIClientError:
                await update.message.reply_text(
                    "❌ Не удалось завершить авторизацию. Попробуйте позже."
                )
                return

            success_text = (
                "✅ Спасибо! Ваш participant_id принят и верифицирован.\n\n"
                "Теперь вы можете пользоваться всеми функциями бота!"
            )
            await update.message.reply_text(success_text)
            context.user_data['student'] = student
            new_bot_user = {"telegram_id": user_id, "student": student, "is_linked": True}
            context.user_data['bot_user'] = new_bot_user
            context.user_data['_bot_user_cache'] = {'data': new_bot_user, 'timestamp': datetime.utcnow()}

        # Сбрасываем состояние пользователя
        user_state.pop(user_id, None)

        # Показываем главное меню
        await show_main_menu(update, context)

    else:
        # participant_id некорректен
        error_text = (
            "❌ Введенный participant_id некорректен.\n\n"
            "Пожалуйста, введите корректный идентификатор участника."
        )
        await update.message.reply_text(error_text)