from pathlib import Path
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.core.database.connection import engine
from src.core.database.models import Directions
from scripts.database_mv.preprocess_excel import preprocess_excel

# === Пути ===
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
FILTERED_FILE = RESULTS_DIR / "filtered_data.xlsx"


def insert_unique_directions():
    # 1️⃣ Предобработка Excel — создаем/обновляем filtered_data.xlsx
    print("🔄 Обработка исходного Excel файла...")
    preprocess_excel()  # создаёт файл filtered_data.xlsx в results/

    # 2️⃣ Загружаем уже обработанный Excel
    if not FILTERED_FILE.exists():
        raise FileNotFoundError(f"❌ Не найден файл {FILTERED_FILE}. Проверь preprocess_excel.")

    df = pd.read_excel(FILTERED_FILE)
    if "Специальность" not in df.columns:
        raise ValueError("❌ В файле нет столбца 'Специальность'. Проверь структуру данных.")

    # 3️⃣ Извлекаем уникальные направления
    unique_dirs = sorted(df["Специальность"].dropna().unique().tolist())
    print(f"📚 Найдено {len(unique_dirs)} направлений. Проверяем дубликаты в БД...")

    # 4️⃣ Добавляем только новые
    with Session(engine) as db:
        existing_titles = {
            d.title.lower() for d in db.scalars(select(Directions.title)).all()
        }

        new_dirs = [d for d in unique_dirs if d.lower() not in existing_titles]
        print(f"🆕 К добавлению: {len(new_dirs)} направлений")

        for title in new_dirs:
            db.add(Directions(title=title))
        db.commit()

        print(f"✅ Добавлено {len(new_dirs)} уникальных направлений")


if __name__ == "__main__":
    insert_unique_directions()
