from telegram import Update
from telegram.ext import ContextTypes
from src.core.database.connection import get_db
from src.core.database.crud.students import get_student_by_participant_id
from src.core.database.crud.bot_users import create_bot_user, get_bot_user_by_telegram_id
from src.bot.services.validation import is_valid_participant_id
from src.bot.middlewares.auth_middleware import allow_unauthorized
from .main_menu import show_main_menu

# Временное хранилище состояния
user_state = {}

@allow_unauthorized
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /start."""
    user = update.effective_user
    user_id = user.id

    # Проверяем, авторизован ли уже пользователь
    db = get_db()
    try:
        bot_user = get_bot_user_by_telegram_id(db, user_id)
        if bot_user and bot_user.is_linked:
            # Пользователь уже авторизован
            await show_main_menu(update, context)
            return
    finally:
        db.close()

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
        db = get_db()
        try:
            from src.core.database.crud.bot_users import get_bot_user_with_student
            bot_user = get_bot_user_with_student(db, user_id)
            if bot_user and bot_user.is_linked:
                await show_main_menu(update, context)
            else:
                await update.message.reply_text(
                    "❌ Вы не авторизованы!\n\n"
                    "Используйте команду /start для авторизации."
                )
        finally:
            db.close()
        return

    # Валидируем participant_id
    if is_valid_participant_id(user_input):
        # Проверяем, существует ли такой студент в базе
        db = get_db()
        try:
            student = get_student_by_participant_id(db, user_input)
            if not student:
                error_text = (
                    "❌ Студент с таким participant_id не найден в системе.\n\n"
                    "Пожалуйста, проверьте правильность ввода и попробуйте еще раз.\n"
                    "Если проблема persists, обратитесь к администратору."
                )
                await update.message.reply_text(error_text)
                return
            
            # Проверяем, не зарегистрирован ли уже этот студент
            bot_user = get_bot_user_by_telegram_id(db, user_id)
            if bot_user:
                if bot_user.student_id == student.id:
                    # Уже зарегистрирован
                    success_text = (
                        "✅ Вы уже авторизованы в системе!\n\n"
                        "Теперь вы можете пользоваться всеми функциями бота!"
                    )
                    await update.message.reply_text(success_text)
                else:
                    # Привязан к другому студенту
                    error_text = (
                        "❌ Этот Telegram аккаунт уже привязан к другому студенту.\n\n"
                        "Если это ошибка, обратитесь к администратору."
                    )
                    await update.message.reply_text(error_text)
                    return
            else:
                # Создаем новую привязку
                create_bot_user(
                    db=db,
                    telegram_id=user_id,
                    student_id=student.id,
                    username=update.effective_user.username
                )
                
                success_text = (
                    "✅ Спасибо! Ваш participant_id принят и верифицирован.\n\n"
                    "Теперь вы можете пользоваться всеми функциями бота!"
                )
                await update.message.reply_text(success_text)

        finally:
            db.close()

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