"""Утилиты для обработки мероприятий: парсинг, форматирование, валидация."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional, Any
import json
from pathlib import Path


def parse_date_string(date_str: str | datetime | Any) -> Optional[datetime]:
    """
    Парсит дату из строки в различных форматах.
    Поддерживаемые форматы:
    - DD.MM.YYYY HH:MM
    - DD.MM.YYYY
    - YYYY-MM-DD HH:MM:SS
    - YYYY-MM-DD
    
    Также поддерживает datetime и date объекты.
    """
    if date_str is None:
        return None
    
    # Если уже datetime объект, возвращаем как есть
    if isinstance(date_str, datetime):
        return date_str
    
    # Если date объект, преобразуем в datetime
    from datetime import date
    if isinstance(date_str, date) and not isinstance(date_str, datetime):
        return datetime.combine(date_str, datetime.min.time())
    
    # Обработка pandas Timestamp
    try:
        import pandas as pd
        if isinstance(date_str, pd.Timestamp):
            return date_str.to_pydatetime()
    except ImportError:
        pass
    
    # Если не строка, пытаемся преобразовать в строку
    if not isinstance(date_str, str):
        date_str = str(date_str)
    
    date_str = date_str.strip()
    if not date_str or date_str.lower() in ['none', 'null', 'nan', '']:
        return None
    
    # Форматы для парсинга
    formats = [
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # Попытка извлечь дату из строки типа "start_date = DD.MM.YYYY HH:MM"
    match = re.search(r'(\d{1,2}[./]\d{1,2}[./]\d{2,4})(?:\s+(\d{1,2}):(\d{2}))?', date_str)
    if match:
        date_part = match.group(1).replace('/', '.')
        time_part = match.group(2) and match.group(3) and f" {match.group(2)}:{match.group(3)}" or ""
        date_str_clean = date_part + time_part
        for fmt in formats:
            try:
                return datetime.strptime(date_str_clean, fmt)
            except ValueError:
                continue
    
    return None


def parse_dates_from_llm_output(dates_text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Парсит даты из вывода LLM в формате:
    start_date = DD.MM.YYYY HH:MM
    end_date = DD.MM.YYYY HH:MM
    """
    if not dates_text:
        return None, None
    
    start_date = None
    end_date = None
    
    # Ищем start_date
    start_match = re.search(r'start_date\s*=\s*([^\n]+)', dates_text, re.IGNORECASE)
    if start_match:
        start_date = parse_date_string(start_match.group(1))
    
    # Ищем end_date
    end_match = re.search(r'end_date\s*=\s*([^\n]+)', dates_text, re.IGNORECASE)
    if end_match:
        end_date = parse_date_string(end_match.group(1))
    
    return start_date, end_date


def parse_online_from_llm_output(online_text: str) -> Optional[bool]:
    """
    Парсит значение online из вывода LLM в формате:
    online = True
    online = False
    online = None
    """
    if not online_text:
        return None
    
    online_text = online_text.strip().lower()
    
    # Ищем паттерн online = True/False/None
    match = re.search(r'online\s*=\s*(true|false|none|null)', online_text, re.IGNORECASE)
    if match:
        value = match.group(1).lower()
        if value == 'true':
            return True
        elif value == 'false':
            return False
        else:
            return None
    
    # Если паттерн не найден, пробуем найти ключевые слова
    if 'online' in online_text and 'true' in online_text:
        return True
    elif 'online' in online_text and 'false' in online_text:
        return False
    elif 'offline' in online_text or 'офлайн' in online_text.lower():
        return False
    elif 'онлайн' in online_text.lower():
        return True
    
    return None


def format_online_to_string(is_online: Optional[bool]) -> Optional[str]:
    """
    Преобразует boolean значение online в строку для поля format в БД.
    """
    if is_online is True:
        return "онлайн"
    elif is_online is False:
        return "офлайн"
    else:
        return None


def format_event_for_db(event: dict[str, Any]) -> dict[str, Any]:
    """
    Форматирует событие для сохранения в БД согласно структуре Events.
    
    Исходные поля:
    - title, link, description, start_date, end_date, image
    
    Обработанные поля (из llm_generator):
    - short_description, dates_extracted_raw, online_extracted_raw, embedding
    
    Возвращает словарь с полями для БД:
    - title, short_description, description, format, start_date, end_date, 
      link, image_url, vector_embedding
    """
    # Парсим даты из исходных данных
    start_date = None
    end_date = None
    
    if event.get("start_date"):
        start_date = parse_date_string(str(event["start_date"]))
    if event.get("end_date"):
        end_date = parse_date_string(str(event["end_date"]))
    
    # Если даты не были в исходных данных или не удалось распарсить, 
    # пытаемся извлечь из LLM вывода
    dates_text = event.get("dates_extracted_raw", "")
    if dates_text:
        parsed_start, parsed_end = parse_dates_from_llm_output(dates_text)
        if parsed_start and not start_date:
            start_date = parsed_start
        if parsed_end and not end_date:
            end_date = parsed_end
    
    # Парсим online/offline
    is_online = None
    
    # Сначала проверяем исходное поле online
    if "online" in event and event["online"] is not None:
        if isinstance(event["online"], bool):
            is_online = event["online"]
        elif isinstance(event["online"], str):
            online_str = str(event["online"]).strip().lower()
            if online_str in ["true", "1", "yes"]:
                is_online = True
            elif online_str in ["false", "0", "no"]:
                is_online = False
    
    # Если не определили из исходных данных, парсим из LLM вывода
    if is_online is None:
        online_text = event.get("online_extracted_raw", "")
        if online_text:
            is_online = parse_online_from_llm_output(online_text)
    
    format_str = format_online_to_string(is_online)
    
    # Формируем результат
    result = {
        "title": safe_strip(event.get("title")) or "",
        "short_description": safe_strip(event.get("short_description")),
        "description": safe_strip(event.get("description")),
        "format": format_str,
        "start_date": start_date.date() if start_date else None,
        "end_date": end_date.date() if end_date else None,
        "link": safe_strip(event.get("link")),
        "image_url": safe_strip(event.get("image")) or safe_strip(event.get("image_url")),
        "vector_embedding": event.get("embedding"),
    }
    
    return result


def save_events_to_json(events: list[dict], output_path: Path, indent: int = 2) -> None:
    """Сохраняет список мероприятий в JSON файл."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Преобразуем даты в строки для JSON
    events_for_json = []
    for event in events:
        event_copy = event.copy()
        
        # Преобразуем date объекты в строки
        if event_copy.get("start_date"):
            date_val = event_copy["start_date"]
            if hasattr(date_val, "isoformat"):
                event_copy["start_date"] = date_val.isoformat()
            else:
                event_copy["start_date"] = str(date_val)
        
        if event_copy.get("end_date"):
            date_val = event_copy["end_date"]
            if hasattr(date_val, "isoformat"):
                event_copy["end_date"] = date_val.isoformat()
            else:
                event_copy["end_date"] = str(date_val)
        
        # Убираем поля, которые не нужны в итоговом JSON (временные поля для обработки)
        event_copy.pop("dates_extracted_raw", None)
        event_copy.pop("online_extracted_raw", None)
        
        events_for_json.append(event_copy)
    
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(events_for_json, f, ensure_ascii=False, indent=indent)
    
    print(f"💾 Сохранено {len(events_for_json)} мероприятий в {output_path}")


def validate_event(event: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Валидирует мероприятие и возвращает (is_valid, list_of_errors).
    """
    errors = []
    
    if not event.get("title"):
        errors.append("Отсутствует поле 'title'")
    
    return len(errors) == 0, errors


def safe_strip(value: Any) -> Optional[str]:
    """Безопасно обрабатывает строковые значения, включая None."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    return str(value).strip() or None


def check_event_exists(db, event: dict[str, Any]) -> bool:
    """
    Проверяет, существует ли мероприятие в БД.
    Учитывает комбинацию title + start_date + link для определения дубликатов.
    
    Логика проверки:
    - Если есть start_date И link: проверка по title + start_date + link
    - Если есть только start_date: проверка по title + start_date
    - Если есть только link: проверка по title + link
    - Если нет ни start_date, ни link: проверка только по title (для регулярных мероприятий)
    
    Args:
        db: SQLAlchemy сессия
        event: словарь с данными мероприятия
    
    Returns:
        True если мероприятие уже существует, False иначе
    """
    from sqlalchemy.orm import Session
    from sqlalchemy import select, and_
    from src.core.database.models import Events
    
    if not isinstance(db, Session):
        raise TypeError("db должен быть SQLAlchemy Session")
    
    title = safe_strip(event.get("title")) or ""
    start_date = event.get("start_date")
    link = safe_strip(event.get("link"))
    
    # Если нет title, не можем проверить
    if not title:
        return False
    
    # Строим условия для поиска
    conditions = [Events.title == title]
    
    # Определяем стратегию проверки в зависимости от наличия полей
    # link считается валидным только если он не None и не пустая строка
    has_link = link is not None and link != ""
    has_start_date = start_date is not None
    
    if has_start_date and has_link:
        # Точное совпадение по title + start_date + link
        conditions.append(Events.start_date == start_date)
        conditions.append(Events.link == link)
    elif has_start_date:
        # Проверка по title + start_date
        conditions.append(Events.start_date == start_date)
    elif has_link:
        # Проверка по title + link
        conditions.append(Events.link == link)
    # Если нет ни start_date, ни link - проверяем только по title
    # (для регулярных мероприятий с одинаковым названием)
    
    stmt = select(Events).where(and_(*conditions))
    existing = db.scalar(stmt)
    return existing is not None


def insert_events_to_db(events: list[dict[str, Any]]) -> tuple[int, int]:
    """
    Добавляет мероприятия в БД, пропуская дубликаты.

    Args:
        events: список словарей с данными мероприятий

    Returns:
        кортеж (добавлено, пропущено)
    """
    from sqlalchemy.orm import Session
    from src.core.database.connection import engine
    from src.core.database.models import Events

    added_count = 0
    skipped_count = 0

    with Session(engine) as db:
        for i, event in enumerate(events, 1):
            try:
                # Проверяем, существует ли мероприятие
                if check_event_exists(db, event):
                    skipped_count += 1
                    if i <= 5 or i % 10 == 0:
                        print(f"   ⏭️  Пропущено (дубликат): {event.get('title', 'Без названия')}")
                    continue

                # Подготавливаем vector_embedding
                vector_embedding = event.get("vector_embedding")
                # Если это список, преобразуем в формат для pgvector
                # pgvector автоматически конвертирует список в Vector при сохранении

                # Создаем новое мероприятие
                new_event = Events(
                    title=event.get("title", ""),
                    short_description=event.get("short_description"),
                    description=event.get("description"),
                    format=event.get("format"),
                    start_date=event.get("start_date"),
                    end_date=event.get("end_date"),
                    link=event.get("link"),
                    image_url=event.get("image_url"),
                    vector_embedding=vector_embedding,  # pgvector автоматически обработает список
                )

                db.add(new_event)
                db.commit()
                db.refresh(new_event)

                added_count += 1
                if added_count <= 5 or added_count % 10 == 0:
                    print(f"   ✅ Добавлено в БД: {event.get('title', 'Без названия')}")

            except Exception as e:
                db.rollback()
                print(f"   ❌ Ошибка при добавлении '{event.get('title', 'Без названия')}': {e}")
                skipped_count += 1
    
    return added_count, skipped_count

