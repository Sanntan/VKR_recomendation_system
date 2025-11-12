from datetime import datetime
from typing import Any, Mapping
from uuid import UUID

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from .recommendations import format_event_card
from src.bot.services.api_client import api_client, APIClientError
from src.bot.middlewares.auth_middleware import auth_required


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            try:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                return None
    return None

def get_search_buttons(event_id: str, is_favorite: bool = False) -> InlineKeyboardMarkup:
    """Создает кнопки для результатов поиска."""
    keyboard = [
        [
            InlineKeyboardButton(
                "❌ Удалить из избранного" if is_favorite else "⭐ В избранное",
                callback_data=f"{'remove_favorite' if is_favorite else 'add_favorite'}_{event_id}"
            )
        ],
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

    try:
        if filter_type == 'all':
            response = await api_client.get_active_events(limit=50)
            events = response.get("events", [])
        elif filter_type == 'recent':
            response = await api_client.get_active_events(limit=50)
            events_raw = response.get("events", [])

            def get_sort_date(event: Mapping[str, Any]) -> datetime:
                start = _parse_datetime(event.get("start_date"))
                created = _parse_datetime(event.get("created_at"))
                return start or created or datetime.min

            events = sorted(events_raw, key=get_sort_date)[:20]
        elif filter_type == 'direction' and student:
            cluster_id = student.get("direction", {}).get("cluster_id") if isinstance(student, Mapping) else None
            if cluster_id:
                response = await api_client.get_events_by_clusters([cluster_id], limit=50)
                events = response.get("events", [])
            else:
                response = await api_client.get_active_events(limit=50)
                events = response.get("events", [])
        else:
            response = await api_client.get_active_events(limit=50)
            events = response.get("events", [])
    except APIClientError:
        await query.edit_message_text(
            "Не удалось загрузить мероприятия. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Назад к поиску", callback_data="event_search")]]
            )
        )
        return

    if not events:
        await query.edit_message_text(
            "По вашему запросу мероприятий не найдено 😔",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Назад к поиску", callback_data="event_search")]]
            )
        )
        return

    context.user_data['search_results'] = [str(event["id"]) for event in events]
    context.user_data['search_events'] = {str(event["id"]): event for event in events}
    context.user_data['current_search_index'] = 0

    event = events[0]
    event_id = str(event["id"])
    
    # Проверяем избранное
    is_favorite = False
    if student:
        try:
            student_uuid = UUID(student.get("id"))
            is_favorite = await api_client.check_favorite(student_uuid, UUID(event_id))
        except (ValueError, TypeError, APIClientError):
            pass
    
    await query.edit_message_text(
        f"🔍 *Найдено мероприятий: {len(events)}*\n\n" + format_event_card(event),
        reply_markup=get_search_buttons(event_id, is_favorite),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

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

    event_id = results[current_index]
    search_cache = context.user_data.get('search_events', {})
    event = search_cache.get(event_id)

    if not event:
        try:
            event_uuid = UUID(event_id)
        except (ValueError, TypeError):
            event_uuid = None

        if event_uuid:
            try:
                event = await api_client.get_event(event_uuid)
            except APIClientError:
                event = None
        else:
            event = None

    if not event:
        await show_search_filters(update, context)
        return

    search_cache[event_id] = event
    context.user_data['search_events'] = search_cache

    # Проверяем избранное
    student = context.user_data.get('student')
    is_favorite = False
    if student:
        try:
            student_uuid = UUID(student.get("id"))
            is_favorite = await api_client.check_favorite(student_uuid, UUID(event_id))
        except (ValueError, TypeError, APIClientError):
            pass

    new_text = f"🔍 *Найдено мероприятий: {len(results)}*\n\n" + format_event_card(event)
    new_markup = get_search_buttons(str(event["id"]), is_favorite)

    current_text = query.message.text if query.message else None
    if current_text and current_text == new_text:
        await query.answer("Это то же самое мероприятие", show_alert=False)
        return

    try:
        await query.edit_message_text(
            new_text,
            reply_markup=new_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    except Exception as e:
        if "not modified" in str(e).lower():
            await query.answer("Это то же самое мероприятие", show_alert=False)
        else:
            raise