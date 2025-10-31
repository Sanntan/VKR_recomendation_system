from sqlalchemy.orm import Session
from datetime import date
from sqlalchemy import text
from uuid import uuid4

from src.core.database.connection import engine

# ✅ Импорты актуальных CRUD
from src.core.database.crud.students import create_student
from src.core.database.crud.directions import create_direction
from src.core.database.crud.clusters import create_cluster
from src.core.database.crud.events import create_event
from src.core.database.crud.event_clusters import add_event_to_cluster
from src.core.database.crud.recommendations import create_recommendation
from src.core.database.crud.feedback import create_feedback


# ✅ Очередность удаления таблиц с учётом foreign keys
TABLES = [
    "recommendations",
    "feedback",
    "event_clusters",
    "events",
    "students",
    "directions",
    "clusters"
]


def reset_database(session: Session):
    print("⚙️ Очистка таблиц перед тестом...\n")

    for table in TABLES:
        session.execute(
            text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
        )

    session.commit()
    print("✅ Таблицы очищены.\n")


def main():
    with Session(engine) as session:
        reset_database(session)

        # === 1. Создаём кластер ===
        cluster = create_cluster(session, title="Программирование")
        print(f"📂 Кластер создан: {cluster.title}")

        # === 2. Создаём направление и привязываем к кластеру ===
        direction = create_direction(session, title="Прикладная информатика", cluster_id=cluster.id)
        print(f"📘 Направление создано: {direction.title} → cluster: {cluster.title}")

        # === 3. Создаём студента ===
        student = create_student(
            db=session,
            participant_id="U-001",
            institution="ТюмГУ",
            direction_id=direction.id,
            profile_embedding=None
        )
        print(f"👨‍🎓 Студент создан: {student.participant_id} → direction: {direction.title}")

        # === 4. Создаём мероприятие ===
        event = create_event(
            db=session,
            title="Хакатон по анализу данных",
            description="Соревнование по Data Science.",
            short_description="Хакатон",
            format="Очно",
            start_date=date(2025, 5, 10),
            end_date=date(2025, 5, 12),
            link="https://leader-id.ru/events/test",
            image_url=None,
            vector_embedding=None,
            cluster_ids=None
        )
        print(f"🎯 Мероприятие создано: {event.title}")

        # === 5. Привязка события к кластеру ===
        add_event_to_cluster(session, event.id, cluster.id)
        print(f"🔗 Event ↔ Cluster связаны: {event.title} → {cluster.title}")

        # === 6. Добавляем рекомендацию ===
        rec = create_recommendation(session, student.id, event.id, score=0.92)
        print(f"💡 Рекомендация создана: student={student.participant_id}, event={event.title}, score={rec.score}")

        # === 7. Добавляем отзыв ===
        fb = create_feedback(session, student.id, rating=5, comment="Очень круто!")
        print(f"📝 Отзыв добавлен: rating={fb.rating}, comment='{fb.comment}'")

        print("\n✅ Все тестовые данные успешно добавлены в базу!\n")


if __name__ == "__main__":
    main()
