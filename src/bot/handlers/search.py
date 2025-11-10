from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from src.core.database.connection import get_db
from src.core.database.crud.events import get_active_events, get_events_by_clusters
from .recommendations import format_event_card
from uuid import UUID
from datetime import datetime, date
from sqlalchemy.orm import joinedload

from src.bot.middlewares.auth_middleware import auth_required

def get_search_buttons(event_id: str) -> InlineKeyboardMarkup:
    """Создает кнопки для результатов поиска."""
    keyboard = [
        [InlineKeyboardButton("➡️ Следующее", callback_data="search_next")],
        [InlineKeyboardButton("🔍 Новый поиск", callback_data="event_search")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

@auth_required
async def show_search_filters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает упрощенные фильтры для поиска мероприятий."""
    keyboard = [
        [InlineKeyboardButton("📅 Ближайшие мероприятия", callback_data="filter_recent")],
        [InlineKeyboardButton("🎯 По моему направлению", callback_data="filter_direction")],
        [InlineKeyboardButton("🔍 Все активные", callback_data="filter_all")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "🔍 *Поиск мероприятий*\n\n"
        "Выберите критерий поиска:\n"
        "• 📅 *Ближайшие* - мероприятия в ближайшее время\n"
        "• 🎯 *По направлению* - мероприятия для вашего направления\n"
        "• 🔍 *Все активные* - полный список мероприятий"
    )

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

@auth_required
async def handle_search_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает выбор фильтра поиска."""
    query = update.callback_query
    await query.answer()

    filter_type = query.data.replace('filter_', '')
    student = context.user_data.get('student')

    db = get_db()
    try:
        if filter_type == 'all':
            events = get_active_events(db, limit=50)
        elif filter_type == 'recent':
            # Получаем мероприятия, отсортированные по дате начала
            # Нормализуем даты для корректного сравнения
            def get_sort_date(event):
                if event.start_date:
                    # Преобразуем date в datetime для сравнения
                    if isinstance(event.start_date, date):
                        return datetime.combine(event.start_date, datetime.min.time())
                    return event.start_date
                return event.created_at or datetime.min
            
            events = sorted(
                get_active_events(db, limit=50),
                key=get_sort_date,
                reverse=False
            )[:20]  # Берем 20 ближайших
        elif filter_type == 'direction' and student:
            # Перезагружаем студента с направлением в текущей сессии
            from src.core.database.models import Students
            from sqlalchemy import select
            stmt = (
                select(Students)
                .options(joinedload(Students.direction))
                .where(Students.id == student.id)
            )
            student_with_direction = db.execute(stmt).scalar_one_or_none()
            
            if student_with_direction and student_with_direction.direction and student_with_direction.direction.cluster_id:
                # Получаем мероприятия по кластеру направления студента
                events = get_events_by_clusters(db, [student_with_direction.direction.cluster_id], limit=50)
            else:
                events = get_active_events(db, limit=50)
        else:
            events = get_active_events(db, limit=50)

        if not events:
            await query.edit_message_text(
                "По вашему запросу мероприятий не найдено 😔",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад к поиску", callback_data="event_search")]]
                )
            )
            return

        # Показываем первое мероприятие из результатов
        context.user_data['search_results'] = [str(e.id) for e in events]
        context.user_data['current_search_index'] = 0

        event = events[0]

        await query.edit_message_text(
            f"🔍 *Найдено мероприятий: {len(events)}*\n\n" + format_event_card(event),
            reply_markup=get_search_buttons(str(event.id)),
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    finally:
        db.close()

@auth_required
async def show_next_search_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает следующий результат поиска."""
    query = update.callback_query
    await query.answer()

    results = context.user_data.get('search_results', [])
    current_index = context.user_data.get('current_search_index', 0)

    if not results:
        await show_search_filters(update, context)
        return

    # Проверяем, есть ли следующее мероприятие
    if len(results) <= 1:
        await query.answer("Это единственное найденное мероприятие", show_alert=False)
        return

    current_index = (current_index + 1) % len(results)
    context.user_data['current_search_index'] = current_index

    event_id = UUID(results[current_index])

    db = get_db()
    try:
        from src.core.database.crud.events import get_event_by_id
        from .recommendations import format_event_card
        event = get_event_by_id(db, event_id)
        if not event:
            await show_search_filters(update, context)
            return

        new_text = f"🔍 *Найдено мероприятий: {len(results)}*\n\n" + format_event_card(event)
        new_markup = get_search_buttons(str(event.id))
        
        # Проверяем, отличается ли новое сообщение от текущего
        current_text = query.message.text if query.message else None
        if current_text and current_text == new_text:
            # Если текст тот же, просто показываем уведомление
            await query.answer("Это то же самое мероприятие", show_alert=False)
            return

        await query.edit_message_text(
            new_text,
            reply_markup=new_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    except Exception as e:
        # Если ошибка "Message is not modified", просто показываем уведомление
        if "not modified" in str(e).lower():
            await query.answer("Это то же самое мероприятие", show_alert=False)
        else:
            raise
    finally:
        db.close()