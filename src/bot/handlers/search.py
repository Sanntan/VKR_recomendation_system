from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from .recommendations import TEST_EVENTS, format_event_card


async def show_search_filters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает фильтры для поиска мероприятий."""
    keyboard = [
        [InlineKeyboardButton("📅 По дате", callback_data="filter_date")],
        [InlineKeyboardButton("🎯 По формату", callback_data="filter_format")],
        [InlineKeyboardButton("💡 По навыкам", callback_data="filter_skills")],
        [InlineKeyboardButton("🔍 Все мероприятия", callback_data="filter_all")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "🔍 *Поиск мероприятий*\n\n"
        "Выберите критерий поиска:\n"
        "• 📅 *По дате* - ближайшие события\n"
        "• 🎯 *По формату* - онлайн/офлайн\n"
        "• 💡 *По навыкам* - развиваемые компетенции\n"
        "• 🔍 *Все мероприятия* - полный список"
    )

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def handle_search_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает выбор фильтра поиска."""
    query = update.callback_query
    await query.answer()

    filter_type = query.data.replace('filter_', '')

    if filter_type == 'all':
        events = TEST_EVENTS
    elif filter_type == 'date':
        events = sorted(TEST_EVENTS, key=lambda x: x['id'])
    elif filter_type == 'format':
        events = [e for e in TEST_EVENTS if 'офлайн' in e['format'].lower()]
    elif filter_type == 'skills':
        events = [e for e in TEST_EVENTS if 'коммуникативность' in e['skills'].lower()]
    else:
        events = TEST_EVENTS

    if not events:
        await query.edit_message_text(
            "По вашему запросу мероприятий не найдено 😔",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Назад к поиску", callback_data="event_search")]])
        )
        return

    # Показываем первое мероприятие из результатов
    context.user_data['search_results'] = events
    context.user_data['current_search_index'] = 0

    event = events[0]

    keyboard = [
        [InlineKeyboardButton("➡️ Следующее", callback_data="search_next")],
        [InlineKeyboardButton("🔍 Новый поиск", callback_data="event_search")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]

    await query.edit_message_text(
        f"🔍 *Найдено мероприятий: {len(events)}*\n\n" + format_event_card(event),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )


async def show_next_search_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает следующий результат поиска."""
    query = update.callback_query
    await query.answer()

    results = context.user_data.get('search_results', [])
    current_index = context.user_data.get('current_search_index', 0)

    if not results:
        await show_search_filters(update, context)
        return

    current_index = (current_index + 1) % len(results)
    context.user_data['current_search_index'] = current_index

    event = results[current_index]

    keyboard = [
        [InlineKeyboardButton("➡️ Следующее", callback_data="search_next")],
        [InlineKeyboardButton("🔍 Новый поиск", callback_data="event_search")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]

    await query.edit_message_text(
        f"🔍 *Найдено мероприятий: {len(results)}*\n\n" + format_event_card(event),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )