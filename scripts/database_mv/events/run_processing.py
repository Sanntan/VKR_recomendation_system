"""Скрипт для обработки мероприятий через LLM и добавления в БД.

Запуск:
    python scripts/database_mv/events/run_processing.py

Доступные режимы:
1 - Обработать все мероприятия через LLM и загрузить в БД
2 - Загрузить в БД из существующего JSON файла (если есть)
"""

import json
from pathlib import Path
from src.recommendation.events import llm_generator
from src.recommendation.events.utils import save_events_to_json, insert_events_to_db

# Конфигурация
SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_FILE = SCRIPT_DIR / "data" / "events.csv"  # Входной файл с мероприятиями
OUTPUT_FILE = SCRIPT_DIR / "data" / "events_processed.json"  # Выходной файл с результатами


def show_menu() -> int:
    """Показывает меню выбора и возвращает выбранный вариант."""
    print("\n" + "="*50)
    print("🎯 ОБРАБОТКА МЕРОПРИЯТИЙ")
    print("="*50)
    print("1 - Обработать все мероприятия через LLM и загрузить в БД")
    print("2 - Загрузить в БД из существующего JSON файла")
    print("="*50)

    while True:
        try:
            choice = int(input("Выберите режим (1 или 2): ").strip())
            if choice in [1, 2]:
                return choice
            else:
                print("❌ Пожалуйста, введите 1 или 2")
        except ValueError:
            print("❌ Пожалуйста, введите число 1 или 2")


def load_events_from_json() -> list[dict]:
    """Загружает мероприятия из JSON файла."""
    if not OUTPUT_FILE.exists():
        print(f"❌ Файл {OUTPUT_FILE} не найден!")
        return []

    try:
        with OUTPUT_FILE.open('r', encoding='utf-8') as f:
            events = json.load(f)
        print(f"✅ Загружено {len(events)} мероприятий из {OUTPUT_FILE}")
        return events
    except (json.JSONDecodeError, Exception) as e:
        print(f"❌ Ошибка загрузки файла {OUTPUT_FILE}: {e}")
        return []


def process_all_events() -> list[dict]:
    """Обрабатывает все мероприятия через LLM."""
    # Проверяем наличие входного файла
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"❌ Файл не найден: {INPUT_FILE}")

    print(f"📥 Загрузка мероприятий из: {INPUT_FILE}")
    raw_events = llm_generator.load_events_csv(str(INPUT_FILE))

    print(f"⚙️  Обработка {len(raw_events)} мероприятий через LLM...")
    processed_events = llm_generator.process_events(raw_events)

    print(f"💾 Сохранение результатов в: {OUTPUT_FILE}")
    save_events_to_json(processed_events, OUTPUT_FILE)

    return processed_events


def load_to_database(events: list[dict]) -> None:
    """Загружает мероприятия в базу данных."""
    if not events:
        print("❌ Нет мероприятий для загрузки в БД")
        return

    print(f"📊 Добавление {len(events)} мероприятий в БД...")
    added, skipped = insert_events_to_db(events)

    print(f"\n✅ Готово!")
    print(f"   📥 Загружено в БД: {added}")
    print(f"   ⏭️  Пропущено (дубликаты): {skipped}")
    print(f"   📝 Всего обработано: {len(events)}")


def main() -> None:
    """Основная функция с меню выбора."""
    try:
        # Показываем меню выбора
        choice = show_menu()

        if choice == 1:
            # Режим 1: Обработать все через LLM
            print("\n🚀 ЗАПУСК ПОЛНОЙ ОБРАБОТКИ ЧЕРЕЗ LLM")
            events = process_all_events()
            load_to_database(events)

        elif choice == 2:
            # Режим 2: Загрузить из JSON
            print("\n🚀 ЗАГРУЗКА ИЗ JSON ФАЙЛА")
            events = load_events_from_json()
            if events:
                load_to_database(events)
            else:
                print("❌ Не удалось загрузить мероприятия из JSON файла")

        print("\n🎉 Работа завершена!")

    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        raise


if __name__ == "__main__":
    main()