from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from src.core.database.connection import get_db
from src.core.database.crud.recommendations import get_recommendations_for_student
from src.core.database.crud.events import get_event_by_id, increment_likes, increment_dislikes
from src.bot.middlewares.auth_middleware import auth_required
from datetime import datetime
from uuid import UUID

def format_event_card(event) -> str:
    """Форматирует карточку мероприятия."""
    start_date = event.start_date.strftime('%d.%m.%Y') if event.start_date else 'Не указана'
    end_date = event.end_date.strftime('%d.%m.%Y') if event.end_date else ''
    
    date_str = start_date
    if end_date and start_date != end_date:
        date_str = f"{start_date} - {end_date}"
    
    text = f"🎯 *{event.title}*\n\n"
    
    if event.short_description:
        text += f"{event.short_description}\n\n"
    
    text += f"📅 Дата: {date_str}\n"
    
    if event.format:
        text += f"🎯 Формат: {event.format}\n"
    
    if event.link:
        text += f"🔗 [Регистрация]({event.link})\n"
    
    text += f"👍 {event.likes_count} 👎 {event.dislikes_count}"
    
    return text

def get_recommendation_buttons(event_id: str) -> InlineKeyboardMarkup:
    """Создает кнопки для взаимодействия с рекомендацией."""
    keyboard = [
        [
            InlineKeyboardButton("👍 Интересно", callback_data=f"like_{event_id}"),
            InlineKeyboardButton("👎 Не интересно", callback_data=f"dislike_{event_id}")
        ],
        [
            InlineKeyboardButton("🔄 Показать другие", callback_data="show_other_events"),
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

@auth_required
async def show_recommendations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает рекомендации пользователю."""
    student = context.user_data.get('student')
    if not student:
        await update.callback_query.edit_message_text(
            "❌ Ошибка: пользователь не найден. Попробуйте авторизоваться заново."
        )
        return

    db = get_db()
    try:
        # Получаем рекомендации для студента
        recommendations = get_recommendations_for_student(db, student.id, limit=10)
        
        if not recommendations:
            await update.callback_query.edit_message_text(
                "Пока нет подходящих мероприятий для рекомендаций.\n"
                "Попробуйте воспользоваться поиском мероприятий!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Поиск мероприятий", callback_data="event_search")]])
            )
            return

        # Берем первую рекомендацию
        rec = recommendations[0]
        event = get_event_by_id(db, rec.event_id)
        
        if not event:
            await update.callback_query.edit_message_text(
                "Ошибка загрузки мероприятия. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]])
            )
            return

        context.user_data['current_recommendations'] = [r.event_id for r in recommendations]
        context.user_data['current_recommendation_index'] = 0

        await update.callback_query.edit_message_text(
            format_event_card(event),
            reply_markup=get_recommendation_buttons(str(event.id)),
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    finally:
        db.close()

@auth_required
async def handle_recommendation_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает feedback по рекомендациям."""
    query = update.callback_query
    await query.answer()

    action, event_id_str = query.data.split('_')
    event_id = UUID(event_id_str)

    db = get_db()
    try:
        if action == 'like':
            increment_likes(db, event_id)
            await query.answer("Спасибо! Учтем ваши предпочтения 👍")
        elif action == 'dislike':
            increment_dislikes(db, event_id)
            # Показываем следующее мероприятие
            await show_next_recommendation(update, context)
            return

        # Для лайка остаемся на текущем мероприятии, но обновляем счетчики
        event = get_event_by_id(db, event_id)
        if event:
            await query.edit_message_text(
                format_event_card(event),
                reply_markup=get_recommendation_buttons(str(event.id)),
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
    finally:
        db.close()

@auth_required
async def show_next_recommendation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает следующую рекомендацию."""
    query = update.callback_query
    await query.answer()

    recommendations = context.user_data.get('current_recommendations', [])
    current_index = context.user_data.get('current_recommendation_index', 0)

    if not recommendations:
        await show_recommendations(update, context)
        return

    # Переходим к следующему мероприятию
    current_index = (current_index + 1) % len(recommendations)
    context.user_data['current_recommendation_index'] = current_index

    event_id = recommendations[current_index]

    db = get_db()
    try:
        event = get_event_by_id(db, event_id)
        if not event:
            await show_recommendations(update, context)
            return

        await query.edit_message_text(
            format_event_card(event),
            reply_markup=get_recommendation_buttons(str(event.id)),
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    finally:
        db.close()