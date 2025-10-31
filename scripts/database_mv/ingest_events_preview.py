from __future__ import annotations
import csv
from datetime import date
from pathlib import Path
import pandas as pd

# импорт строго по пути файла (никаких __init__.py)
from src.recommendation.events.mapping import map_csv_row, compute_is_active
from src.recommendation.events.llm_generator import generate_short_and_format

# === Пути ===
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

CSV_PATH = Path("events.csv")  # CSV лежит в корне проекта
OUTPUT_PATH = RESULTS_DIR / "generated_events.xlsx"


def main():
    if not CSV_PATH.exists():
        raise SystemExit(f"❌ Не найден входной файл: {CSV_PATH}")

    events_data = []
    print(f"📄 Загружаем CSV: {CSV_PATH}")

    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            csv_event = map_csv_row(row)
            short_desc, fmt = generate_short_and_format(csv_event.title, csv_event.description)
            active = compute_is_active(date.today(), csv_event.start_date, csv_event.end_date)

            events_data.append({
                "№": i,
                "title": csv_event.title,
                "short_description": short_desc,
                "format": fmt,
                "description": csv_event.description,
                "start_date": csv_event.start_date,
                "end_date": csv_event.end_date,
                "is_active": active,
                "link": csv_event.link,
                "image_url": csv_event.image_url,
            })

            print(f"✅ {i}. {csv_event.title[:60]}... → {fmt}, актуально: {active}")

    df = pd.DataFrame(events_data)
    df.to_excel(OUTPUT_PATH, index=False)

    print(f"\n📊 Готово! Файл сохранён: {OUTPUT_PATH.absolute()}")


if __name__ == "__main__":
    main()
