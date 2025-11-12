from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from uuid import UUID
from typing import Any, Dict

from src.bot.services.api_client import api_client, APIClientError
from src.bot.middlewares.auth_middleware import auth_required
from .recommendations import format_event_card


def get_favorite_buttons(event_id: str, is_favorite: bool = False) -> InlineKeyboardMarkup:
    """Создает кнопки для избранного мероприятия."""
    keyboard = [
        [
            InlineKeyboardButton(
                "❌ Удалить из избранного" if is_favorite else "⭐ Добавить в избранное",
                callback_data=f"{'remove_favorite' if is_favorite else 'add_favorite'}_{event_id}"
            )
        ],
        [
            InlineKeyboardButton("➡️ Следующее", callback_data="favorite_next"),
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


@auth_required
async def show_personal_cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает личный кабинет пользователя."""
    student = context.user_data.get('student')
    if not student:
        await update.callback_query.edit_message_text(
            "❌ Ошибка: пользователь не найден. Попробуйте авторизоваться заново."
        )
        return

    student_id = student.get("id")
    if not student_id:
        await update.callback_query.edit_message_text(
            "❌ Ошибка: не найден идентификатор студента."
        )
        return

    try:
        student_uuid = UUID(student_id)
    except (ValueError, TypeError):
        await update.callback_query.edit_message_text(
            "Ошибка идентификации студента. Попробуйте авторизоваться заново."
        )
        return

    try:
        favorites_count = await api_client.get_favorites_count(student_uuid)
    except APIClientError:
        favorites_count = 0

    keyboard = [
        [InlineKeyboardButton(f"⭐ Избранные ({favorites_count})", callback_data="my_favorites")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "⭐ *Личный кабинет*\n\n"
        f"📊 *Статистика:*\n"
        f"• Избранных мероприятий: {favorites_count}\n\n"
        "Выберите раздел:"
    )

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


@auth_required
async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает избранные мероприятия пользователя."""
    student = context.user_data.get('student')
    if not student:
        await update.callback_query.edit_message_text(
            "❌ Ошибка: пользователь не найден. Попробуйте авторизоваться заново."
        )
        return

    student_id = student.get("id")
    if not student_id:
        await update.callback_query.edit_message_text(
            "❌ Ошибка: не найден идентификатор студента."
        )
        return

    try:
        student_uuid = UUID(student_id)
    except (ValueError, TypeError):
        await update.callback_query.edit_message_text(
            "Ошибка идентификации студента. Попробуйте авторизоваться заново."
        )
        return

    try:
        favorites = await api_client.get_favorites(student_uuid, limit=100)
    except APIClientError:
        await update.callback_query.edit_message_text(
            "Не удалось загрузить избранные мероприятия. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]])
        )
        return

    if not favorites:
        await update.callback_query.edit_message_text(
            "⭐ У вас пока нет избранных мероприятий.\n\n"
            "Добавьте мероприятия в избранное, чтобы они отображались здесь!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="personal_cabinet")]])
        )
        return

    # Сохраняем избранные в контекст
    context.user_data['current_favorites'] = favorites
    context.user_data['current_favorite_index'] = 0

    # Получаем информацию о первом мероприятии
    first_fav = favorites[0]
    event = first_fav.get("event")
    
    if not event:
        await update.callback_query.edit_message_text(
            "Ошибка загрузки мероприятия. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="personal_cabinet")]])
        )
        return

    event_id = str(event.get("id"))
    is_fav = True  # Уже в избранном

    text = f"⭐ *Избранные мероприятия ({len(favorites)})*\n\n" + format_event_card(event)
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=get_favorite_buttons(event_id, is_fav),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )


@auth_required
async def handle_favorite_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает добавление/удаление из избранного."""
    query = update.callback_query
    await query.answer()

    # Парсим callback_data: "add_favorite_{event_id}" или "remove_favorite_{event_id}"
    parts = query.data.split('_', 2)
    if len(parts) < 3:
        await query.answer("Ошибка обработки запроса", show_alert=True)
        return
    
    action = parts[0]  # "add" или "remove"
    event_id_str = parts[2]  # UUID мероприятия
    event_uuid = UUID(event_id_str)

    student = context.user_data.get('student')
    if not student:
        await query.answer("Ошибка: пользователь не найден", show_alert=True)
        return

    student_id = student.get("id")
    if not student_id:
        await query.answer("Ошибка: не найден идентификатор студента", show_alert=True)
        return

    try:
        student_uuid = UUID(student_id)
    except (ValueError, TypeError):
        await query.answer("Ошибка идентификации студента", show_alert=True)
        return

    try:
        if action == 'add':
            await api_client.add_favorite(student_uuid, event_uuid)
            await query.answer("✅ Добавлено в избранное!")
            is_favorite = True
        elif action == 'remove':
            await api_client.remove_favorite(student_uuid, event_uuid)
            await query.answer("❌ Удалено из избранного")
            is_favorite = False
        else:
            return
    except APIClientError as e:
        if "409" in str(e) or "уже в избранном" in str(e).lower():
            await query.answer("⚠️ Уже в избранном", show_alert=False)
            is_favorite = True
        elif "404" in str(e) or "не найдено" in str(e).lower():
            await query.answer("⚠️ Не найдено в избранном", show_alert=False)
            is_favorite = False
        else:
            await query.answer("Ошибка при обработке запроса", show_alert=True)
            return

    # Обновляем текущее сообщение с новым статусом избранного
    # Пытаемся найти событие в текущем контексте
    event = None
    current_text = query.message.text if query.message else ""
    
    # Проверяем разные источники события
    if 'current_favorites' in context.user_data:
        favorites = context.user_data.get('current_favorites', [])
        for fav in favorites:
            if str(fav.get("event", {}).get("id")) == event_id_str:
                event = fav.get("event")
                break
    elif 'search_events' in context.user_data:
        event = context.user_data.get('search_events', {}).get(event_id_str)
    elif 'recommendations_events' in context.user_data:
        event = context.user_data.get('recommendations_events', {}).get(event_id_str)
    
    # Если не нашли, пытаемся загрузить
    if not event:
        try:
            event = await api_client.get_event(event_uuid)
        except APIClientError:
            pass
    
    if event:
        # Определяем, откуда пришли (поиск, рекомендации, избранное)
        if "Избранные мероприятия" in current_text:
            text = f"⭐ *Избранные мероприятия*\n\n" + format_event_card(event)
            await query.edit_message_text(
                text,
                reply_markup=get_favorite_buttons(event_id_str, is_favorite),
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        elif "Найдено мероприятий" in current_text:
            results = context.user_data.get('search_results', [])
            text = f"🔍 *Найдено мероприятий: {len(results)}*\n\n" + format_event_card(event)
            from .search import get_search_buttons
            await query.edit_message_text(
                text,
                reply_markup=get_search_buttons(event_id_str, is_favorite),
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        else:
            # Рекомендации
            from .recommendations import get_recommendation_buttons
            await query.edit_message_text(
                format_event_card(event),
                reply_markup=get_recommendation_buttons(event_id_str, is_favorite),
                parse_mode='Markdown',
                disable_web_page_preview=True
            )


@auth_required
async def show_next_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает следующее избранное мероприятие."""
    query = update.callback_query
    await query.answer()

    favorites = context.user_data.get('current_favorites', [])
    current_index = context.user_data.get('current_favorite_index', 0)

    if not favorites:
        await show_favorites(update, context)
        return

    # Переходим к следующему
    current_index = (current_index + 1) % len(favorites)
    context.user_data['current_favorite_index'] = current_index

    favorite = favorites[current_index]
    event = favorite.get("event")

    if not event:
        await show_favorites(update, context)
        return

    event_id = str(event.get("id"))
    text = f"⭐ *Избранные мероприятия ({len(favorites)})*\n\n" + format_event_card(event)

    await query.edit_message_text(
        text,
        reply_markup=get_favorite_buttons(event_id, True),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

