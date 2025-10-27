from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")
HOST = os.getenv("HOST")
PORT = os.getenv("PORT")
DBNAME = os.getenv("DBNAME")

DATABASE_URL = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

try:
    with engine.connect() as connection:
        print("✅ Connection successful!")

        # 1️⃣ Текущее время на сервере
        result = connection.execute(text("SELECT NOW();"))
        current_time = result.scalar()
        print(f"🕒 Current Time: {current_time}")

        # 2️⃣ Список таблиц в схеме public
        print("\n📋 Existing tables in schema 'public':")
        tables_query = text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        result = connection.execute(tables_query)
        tables = result.fetchall()

        if tables:
            for (table_name,) in tables:
                print(f"   • {table_name}")
        else:
            print("   (no tables found)")

except Exception as e:
    print(f"❌ Failed to connect: {e}")
