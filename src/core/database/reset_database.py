# src/core/reset_database.py
from sqlalchemy import text
from src.core.database.connection import engine

# Порядок важен из-за внешних ключей
TABLES = [
    "recommendations",
    "feedback",
    "event_clusters",
    "events",
    "bot_users",
    "students",
    "directions",
    "clusters"
]

def reset_database():
    with engine.begin() as conn:
        print("⚠️  Удаление всех данных и сброс счётчиков...")
        for table in TABLES:
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
            print(f"   • Очищена таблица: {table}")
        print("\n✅ Все таблицы очищены и ID сброшены!")

if __name__ == "__main__":
    try:
        reset_database()
    except Exception as e:
        print(f"❌ Ошибка при очистке БД: {e}")
