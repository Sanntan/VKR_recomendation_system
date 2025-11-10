"""Unified CLI for managing database content and preprocessing artifacts."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

# Ensure project root is importable when running as a script
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.database.reset_database import reset_database
from src.recommendation.events.utils import (
    insert_events_to_db,
    load_events_from_json_file,
    process_events_from_csv,
)
from src.recommendation.events.score_calculation import recalculate_scores_for_all_students

from scripts.database_mv.helpers.directions_clusters import run_directions_pipeline
from scripts.database_mv.helpers.preprocess_excel import (
    INPUT_FILE as DIRECTIONS_INPUT_FILE,
    OUTPUT_FILE as DIRECTIONS_OUTPUT_FILE,
    preprocess_excel,
)

# Base directories
BASE_DIR = CURRENT_FILE.parent
SOURCES_DIR = BASE_DIR / "sources"
RESULTS_DIR = BASE_DIR / "results"

EVENTS_SOURCES_DIR = SOURCES_DIR / "events"
EVENTS_RESULTS_DIR = RESULTS_DIR / "events"

EVENTS_INPUT_FILE = EVENTS_SOURCES_DIR / "events.csv"
EVENTS_OUTPUT_FILE = EVENTS_RESULTS_DIR / "events_processed.json"

CLUSTER_TOP_K = 3
SIMILARITY_THRESHOLD = 0.35


def _ensure_event_paths() -> None:
    EVENTS_SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    EVENTS_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _prompt_choice(prompt: str, valid: set[int]) -> int:
    while True:
        try:
            choice = int(input(prompt).strip())
        except ValueError:
            print("❌ Пожалуйста, введите номер пункта меню")
            continue

        if choice in valid:
            return choice

        print("❌ Пожалуйста, выберите один из пунктов меню")


def run_events_menu() -> None:
    _ensure_event_paths()

    while True:
        print("\n" + "=" * 50)
        print("🎯 ОБРАБОТКА МЕРОПРИЯТИЙ")
        print("=" * 50)
        print("📂 CSV ожидается в:", EVENTS_INPUT_FILE)
        print("💾 JSON сохраняется в:", EVENTS_OUTPUT_FILE)
        print("1 - Обработать CSV и сохранить JSON")
        print("2 - Загрузить мероприятия из JSON в БД")
        print("3 - Загрузить мероприятия и распределить по кластерам")
        print("4 - Пересчитать scores между студентами и мероприятиями")
        print("0 - Назад")
        print("=" * 50)

        choice = _prompt_choice("Выберите режим: ", {0, 1, 2, 3, 4})

        if choice == 0:
            return

        if choice == 1:
            print("\n🚀 ОБРАБОТКА CSV -> JSON")
            try:
                events = process_events_from_csv(EVENTS_INPUT_FILE, EVENTS_OUTPUT_FILE)
                print(
                    f"\n✅ Обработка завершена. Получено {len(events)} мероприятий."
                )
            except FileNotFoundError as exc:
                print(str(exc))
            except Exception as exc:  # noqa: BLE001 - выводим подробности пользователю
                print(f"💥 Ошибка обработки: {exc}")

        elif choice in (2, 3):
            print("\n🚀 ЗАГРУЗКА МЕРОПРИЯТИЙ ИЗ JSON")
            events = load_events_from_json_file(EVENTS_OUTPUT_FILE)
            if not events:
                continue

            assign_clusters = choice == 3
            if assign_clusters:
                print("📌 Привязка мероприятий к кластерам включена")

            try:
                added, skipped = insert_events_to_db(
                    events,
                    assign_clusters=assign_clusters,
                    cluster_top_k=CLUSTER_TOP_K,
                    similarity_threshold=SIMILARITY_THRESHOLD,
                )
                print("\n✅ Загрузка завершена!")
                print(f"   📥 Вставлено: {added}")
                print(f"   ⏭️  Пропущено: {skipped}")
                print(f"   📝 Всего в JSON: {len(events)}")
            except Exception as exc:  # noqa: BLE001
                print(f"💥 Ошибка загрузки в БД: {exc}")

        elif choice == 4:
            print("\n🚀 ПЕРЕСЧЕТ SCORES МЕЖДУ СТУДЕНТАМИ И МЕРОПРИЯТИЯМИ")
            try:
                from src.core.database.connection import get_db
                db = get_db()
                try:
                    stats = recalculate_scores_for_all_students(db, min_score=0.0)
                    print(f"\n✅ Пересчет завершен успешно!")
                    print(f"   📊 Статистика:")
                    print(f"      - Рассчитано пар: {stats['total_calculated']}")
                    print(f"      - Сохранено рекомендаций: {stats['total_saved']}")
                    print(f"      - Обработано студентов: {stats['students_processed']}")
                    print(f"      - Обработано мероприятий: {stats['events_processed']}")
                finally:
                    db.close()
            except Exception as exc:  # noqa: BLE001
                print(f"💥 Ошибка пересчета scores: {exc}")


def run_directions_menu() -> None:
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    DIRECTIONS_INPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    DIRECTIONS_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    while True:
        print("\n" + "=" * 50)
        print("🧭 НАПРАВЛЕНИЯ И КЛАСТЕРЫ")
        print("=" * 50)
        print("📂 Исходный Excel ожидается в:", DIRECTIONS_INPUT_FILE)
        print("💾 Результат предобработки сохраняется в:", DIRECTIONS_OUTPUT_FILE)
        print("1 - Предобработать Excel")
        print("2 - Кластеризовать направления и загрузить в БД")
        print("0 - Назад")
        print("=" * 50)

        choice = _prompt_choice("Выберите режим: ", {0, 1, 2})

        if choice == 0:
            return

        if choice == 1:
            try:
                preprocess_excel()
                print("\n✅ Предобработка завершена!")
            except FileNotFoundError as exc:
                print(str(exc))
            except Exception as exc:  # noqa: BLE001
                print(f"💥 Ошибка предобработки: {exc}")

        elif choice == 2:
            try:
                run_directions_pipeline(force_preprocess=False)
                print("\n✅ Кластеризация направлений завершена!")
            except FileNotFoundError as exc:
                print(str(exc))
            except Exception as exc:  # noqa: BLE001
                print(f"💥 Ошибка кластеризации: {exc}")


def show_main_menu() -> int:
    print("\n" + "=" * 60)
    print("🛠️  УТИЛИТЫ УПРАВЛЕНИЯ БД")
    print("=" * 60)
    print("1 - Действия с мероприятиями")
    print("2 - Действия с направлениями и кластерами")
    print("9 - Сбросить базу данных")
    print("0 - Выйти")
    print("=" * 60)
    return _prompt_choice("Выберите режим: ", {0, 1, 2, 9})


def run_reset_database() -> None:
    confirm = input("\n⚠️  Это удалит все данные. Продолжить? (yes/no): ").strip().lower()
    if confirm in {"y", "yes", "д", "да"}:
        reset_database()
    else:
        print("🚫 Операция сброса отменена")


def main() -> None:
    actions: dict[int, Callable[[], None] | None] = {
        1: run_events_menu,
        2: run_directions_menu,
        9: run_reset_database,
    }

    while True:
        choice = show_main_menu()

        if choice == 0:
            print("\n👋 Выход из программы")
            return

        action = actions.get(choice)
        if action is None:
            print("❌ Неизвестный выбор. Попробуйте снова.")
            continue

        action()


if __name__ == "__main__":
    main()
