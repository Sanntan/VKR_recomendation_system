"""Вспомогательный скрипт для массовой обработки мероприятий через LLM.

Скрипт выступает в роли обёртки над функциями из
``src.recommendation.events.llm_generator`` и позволяет запускать их в
непосредственно на GPU. За счёт того, что ``llm_generator`` инициализирует
модели в CUDA-контексте при импорте, достаточно вызвать обработку
мероприятий, чтобы модели были автоматически выгружены на доступный GPU.

Пример запуска:

```
python scripts/database_mv/events/run_processing.py \
    --input ./data/events.csv \
    --output ./data/events_processed.json \
    --limit 100
```

Для корректной работы убедитесь, что в окружении установлены зависимости
``torch`` (с поддержкой CUDA), ``unsloth`` и ``sentence-transformers``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Optional

from src.recommendation.events.llm_generator import load_events_csv, process_events


def parse_args() -> argparse.Namespace:
    """Считывает аргументы командной строки."""

    parser = argparse.ArgumentParser(description="Обработка мероприятий при помощи LLM")
    parser.add_argument(
        "--input",
        type=str,
        default="events.csv",
        help="Путь к CSV-файлу с мероприятиями (по умолчанию events.csv в директории скрипта)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Ограничить количество обрабатываемых записей",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Путь для сохранения результатов в JSON. Если не указан, данные не сохраняются",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Отступ для JSON-файла (актуален только при указании --output)",
    )
    return parser.parse_args()


def resolve_path(path: str, default_dir: Path) -> Path:
    """Преобразует относительный путь относительно ``default_dir``."""

    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return default_dir / path_obj


def ensure_parent_dir(path: Path) -> None:
    """Создаёт директорию для файла, если она ещё не существует."""

    if path.parent.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)


def write_results(path: Path, processed: Iterable[dict], indent: int = 2) -> None:
    """Сохраняет обработанные данные в JSON."""

    ensure_parent_dir(path)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(list(processed), output_file, ensure_ascii=False, indent=indent)


def main() -> None:
    args = parse_args()

    script_dir = Path(__file__).resolve().parent
    input_path = resolve_path(args.input, script_dir)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Не удалось найти CSV-файл с мероприятиями по пути: {input_path}"
        )

    print(f"📥 Загружаем мероприятия из: {input_path}")
    events = load_events_csv(str(input_path))
    limit: Optional[int] = args.limit
    if limit is not None and limit <= 0:
        raise ValueError("Параметр --limit должен быть положительным числом")

    print("⚙️  Запускаем обработку через llm_generator...")
    processed = process_events(events, limit=limit)

    print(f"\n✅ Всего обработано: {len(processed)}")

    if args.output:
        output_path = resolve_path(args.output, script_dir)
        write_results(output_path, processed, indent=args.indent)
        print(f"💾 Результаты сохранены в: {output_path}")


if __name__ == "__main__":
    main()
