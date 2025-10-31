from __future__ import annotations
import csv
from pathlib import Path
from src.core.database.connection import get_db
from src.recommendation.events.mapping import map_csv_row
from src.recommendation.events.pipeline import upsert_event

CSV_PATH = Path("results.csv")  # ← корень проекта

def main():
    inserted, updated = 0, 0

    with next(get_db()) as db:
        with CSV_PATH.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ev = map_csv_row(row)
                event_id, status = upsert_event(db, ev)
                if status == "inserted":
                    inserted += 1
                else:
                    updated += 1

    print(f"✅ Импорт завершён. Добавлено: {inserted}, обновлено: {updated}")

if __name__ == "__main__":
    main()
