# src/core/reset_database.py
from sqlalchemy import text
from src.core.database.connection import engine

TABLES = [
    "recommendations",
    "feedback",
    "event_categories",
    "category_directions",
    "events",
    "categories",
    "directions",
    "bot_users",
    "students"
]

def reset_database():
    with engine.begin() as conn:
        print("⚠️  Удаление всех данных и сброс счётчиков...")
        for table in TABLES:
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
            print(f"   • Очищена таблица {table}")
        print("\n✅ Все таблицы очищены и счётчики ID сброшены.")

if __name__ == "__main__":
    try:
        reset_database()
    except Exception as e:
        print(f"❌ Ошибка при очистке БД: {e}")
