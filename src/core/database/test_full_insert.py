from sqlalchemy.orm import Session
from datetime import date
from src.core.database.connection import engine

# CRUD-модули
from src.core.database.crud.students import create_student
from src.core.database.crud.directions import create_direction
from src.core.database.crud.categories import create_category
from src.core.database.crud.events import create_event
from src.core.database.crud.recommendations import create_recommendation
from src.core.database.crud.feedback import create_feedback
from src.core.database.crud.category_directions import create_category_direction
from src.core.database.crud.event_categories import create_event_category

# Таблицы для очистки (важно соблюдать порядок, чтобы не нарушать внешние ключи)
from sqlalchemy import text

TABLES = [
    "recommendations",
    "feedback",
    "event_categories",
    "category_directions",
    "events",
    "categories",
    "directions",
    "students"
]

def reset_database(session: Session):
    print("⚙️ Очистка таблиц перед тестом...")
    for table in TABLES:
        session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
    session.commit()
    print("✅ Таблицы очищены.\n")


def main():
    with Session(engine) as session:
        # Очистим БД
        reset_database(session)

        # === 1. Добавляем студента ===
        student = create_student(
            db=session,
            participant_id="U-001",
            institution="ТюмГУ",
            specialty="Прикладная информатика"
        )
        print(f"👨‍🎓 Добавлен студент: {student.specialty} ({student.participant_id})")

        # === 2. Добавляем направление ===
        direction = create_direction(session, title="IT-направление")
        print(f"📘 Добавлено направление: {direction.title}")

        # === 3. Добавляем категорию ===
        category = create_category(session, title="Программирование")
        print(f"🏷️ Добавлена категория: {category.title}")

        # === 4. Создаём связь категория ↔ направление ===
        create_category_direction(session, category.id, direction.id)
        print("🔗 Связь категория ↔ направление создана")

        # === 5. Добавляем мероприятие ===
        event = create_event(
            db=session,
            title="Хакатон по анализу данных",
            description="Мероприятие для студентов IT-направлений.",
            format="очное",
            start_date=date(2025, 5, 10),
            end_date=date(2025, 5, 12),
            link="https://leader-id.ru/events/test"
        )
        print(f"🎯 Добавлено мероприятие: {event.title}")

        # === 6. Связываем мероприятие с категорией ===
        create_event_category(session, event.id, category.id)
        print("🔗 Связь мероприятие ↔ категория создана")

        # === 7. Добавляем рекомендацию студенту ===
        rec = create_recommendation(session, student.id, event.id, score=0.92)
        print(f"💡 Добавлена рекомендация: student={student.participant_id}, event={event.title}, score={rec.score}")

        # === 8. Добавляем отзыв ===
        fb = create_feedback(session, student.id, rating=5, comment="Очень полезное мероприятие!")
        print(f"📝 Отзыв добавлен: rating={fb.rating}, comment='{fb.comment}'")

        print("\n✅ Все тестовые данные успешно добавлены в базу данных!")

if __name__ == "__main__":
    main()
