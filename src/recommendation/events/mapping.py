from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

def parse_date_safe(value: str | None) -> Optional[date]:
    """Безопасный парсер дат из CSV."""
    if not value or not str(value).strip():
        return None
    v = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(v[:10]).date()
    except Exception:
        return None

def compute_is_active(today: date, start: Optional[date], end: Optional[date]) -> bool:
    """Возвращает True, если мероприятие актуально (идёт или ожидается)."""
    if start is None and end is None:
        return True
    if start and end:
        return end >= today
    if start and not end:
        return start >= today
    if end and not start:
        return end >= today
    return True

@dataclass
class CSVEvent:
    title: str
    link: str
    description: str
    start_date: Optional[date]
    end_date: Optional[date]
    image_url: Optional[str]

def map_csv_row(row: dict[str, str]) -> CSVEvent:
    return CSVEvent(
        title=(row.get("title") or "").strip(),
        link=(row.get("link") or "").strip(),
        description=(row.get("description") or "").strip(),
        start_date=parse_date_safe(row.get("start_date")),
        end_date=parse_date_safe(row.get("end_date")),
        image_url=(row.get("image") or "").strip() or None,
    )
