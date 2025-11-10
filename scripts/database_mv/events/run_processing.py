"""Консольное меню для обработки и загрузки мероприятий."""

from pathlib import Path

from src.recommendation.events.utils import (
    insert_events_to_db,
    load_events_from_json_file,
    process_events_from_csv,
)

# Конфигурация
SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_FILE = SCRIPT_DIR / "data" / "events.csv"  # Входной файл с мероприятиями
OUTPUT_FILE = SCRIPT_DIR / "data" / "events_processed.json"  # Выходной файл с результатами
CLUSTER_TOP_K = 3
SIMILARITY_THRESHOLD = 0.35


def show_menu() -> int:
    """Показывает меню выбора и возвращает выбранный вариант."""
    print("\n" + "=" * 50)
    print("🎯 ОБРАБОТКА МЕРОПРИЯТИЙ")
    print("=" * 50)
    print("1 - Обработать CSV и сохранить JSON")
    print("2 - Загрузить мероприятия из JSON в БД")
    print("3 - Загрузить мероприятия и распределить по кластерам")
    print("0 - Выйти")
    print("=" * 50)

    while True:
        try:
            choice = int(input("Выберите режим: ").strip())
            if choice in [0, 1, 2, 3]:
                return choice
            print("❌ Пожалуйста, выберите один из пунктов меню")
        except ValueError:
            print("❌ Пожалуйста, введите номер пункта меню")


def main() -> None:
    """Запускает циклическое меню для обработки мероприятий."""

    while True:
        choice = show_menu()

        if choice == 0:
            print("\n👋 Выход из программы")
            break

        if choice == 1:
            print("\n🚀 ОБРАБОТКА CSV -> JSON")
            try:
                events = process_events_from_csv(INPUT_FILE, OUTPUT_FILE)
                print(f"\n✅ Обработка завершена. Получено {len(events)} мероприятий.")
            except FileNotFoundError as exc:
                print(str(exc))
            except Exception as exc:
                print(f"💥 Ошибка обработки: {exc}")

        elif choice in (2, 3):
            print("\n🚀 ЗАГРУЗКА МЕРОПРИЯТИЙ ИЗ JSON")
            events = load_events_from_json_file(OUTPUT_FILE)
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
            except Exception as exc:
                print(f"💥 Ошибка загрузки в БД: {exc}")


if __name__ == "__main__":
    main()
