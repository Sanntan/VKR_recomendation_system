from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import random
from datetime import datetime, timedelta

# Тестовые данные мероприятий
TEST_EVENTS = [
    {
        'id': 1,
        'title': 'Воркшоп по лидерству',
        'date': (datetime.now() + timedelta(days=5)).strftime('%d %B'),
        'format': 'офлайн (Центр компетенций, ауд. 202)',
        'skills': 'коммуникативность, ориентация на результат',
        'registration_link': 'https://example.com/event1'
    },
    {
        'id': 2,
        'title': 'Мастер-класс по Python',
        'date': (datetime.now() + timedelta(days=3)).strftime('%d %B'),
        'format': 'онлайн (Zoom)',
        'skills': 'программирование, аналитическое мышление',
        'registration_link': 'https://example.com/event2'
    },
    {
        'id': 3,
        'title': 'Кейс-чемпионат по маркетингу',
        'date': (datetime.now() + timedelta(days=7)).strftime('%d %B'),
        'format': 'гибридный (офлайн + стрим)',
        'skills': 'стратегическое мышление, работа в команде',
        'registration_link': 'https://example.com/event3'
    },
    {
        'id': 4,
        'title': 'Лекция по искусственному интеллекту',
        'date': (datetime.now() + timedelta(days=2)).strftime('%d %B'),
        'format': 'офлайн (Главный корпус, ауд. 301)',
        'skills': 'технические навыки, креативность',
        'registration_link': 'https://example.com/event4'
    }
]


def format_event_card(event: dict) -> str:
    """Форматирует карточку мероприятия."""
    return (
        f"🎯 *{event['title']}*\n\n"
        f"📅 Дата: {event['date']}\n"
        f"📍 Формат: {event['format']}\n"
        f"💡 Развивает: {event['skills']}\n"
        f"🔗 [Перейти к регистрации]({event['registration_link']})"
    )


def get_recommendation_buttons(event_id: int) -> InlineKeyboardMarkup:
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


async def show_recommendations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает рекомендации пользователю."""
    # Берем случайные мероприятия для демонстрации
    recommended_events = random.sample(TEST_EVENTS, min(3, len(TEST_EVENTS)))

    if not recommended_events:
        await update.callback_query.edit_message_text(
            "Пока нет подходящих мероприятий для рекомендаций. Попробуйте позже!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]])
        )
        return

    # Показываем первое мероприятие
    event = recommended_events[0]
    context.user_data['current_recommendations'] = recommended_events
    context.user_data['current_recommendation_index'] = 0

    await update.callback_query.edit_message_text(
        format_event_card(event),
        reply_markup=get_recommendation_buttons(event['id']),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def handle_recommendation_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает feedback по рекомендациям."""
    query = update.callback_query
    await query.answer()

    action, event_id = query.data.split('_')
    event_id = int(event_id)

    if action == 'like':
        # Сохраняем положительный feedback
        if 'liked_events' not in context.user_data:
            context.user_data['liked_events'] = []
        context.user_data['liked_events'].append(event_id)
        await query.answer("Спасибо! Учтем ваши предпочтения 👍")

    elif action == 'dislike':
        # Сохраняем отрицательный feedback
        if 'disliked_events' not in context.user_data:
            context.user_data['disliked_events'] = []
        context.user_data['disliked_events'].append(event_id)
        await query.answer("Понятно, учтем ваши предпочтения 👎")


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

    event = recommendations[current_index]

    await query.edit_message_text(
        format_event_card(event),
        reply_markup=get_recommendation_buttons(event['id']),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )