from __future__ import annotations
import re, json
from typing import Tuple
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

_MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

print("[INFO] Загрузка TinyLlama модели (один раз при запуске)...")
tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(_MODEL_NAME, torch_dtype="auto", device_map="auto")

generator = pipeline("text-generation", model=model, tokenizer=tokenizer, max_new_tokens=250, temperature=0.3, do_sample=False)

def _truncate(text: str, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")

def _heuristic_format(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    if any(k in text for k in ["онлайн", "online", "вебинар", "zoom", "teams", "youtube"]):
        return "Онлайн"
    if any(k in text for k in ["офлайн", "адрес", "зал", "аудитор", "очный"]):
        return "Оффлайн"
    return "Онлайн"

def generate_short_and_format(title: str, description: str) -> Tuple[str, str]:
    """Создаёт краткое описание и формат (TinyLlama офлайн)."""
    prompt = (
        "Ты редактор карточек Telegram-бота.\n"
        "1) Сформулируй краткое описание (до 280 символов, без эмодзи, без хэштегов).\n"
        "2) Определи формат: Онлайн или Оффлайн.\n\n"
        f"Заголовок: {title}\nОписание: {description}\n\n"
        "Ответ верни строго в JSON: {\"short\":\"...\",\"format\":\"Онлайн|Оффлайн\"}"
    )

    try:
        result = generator(prompt)[0]["generated_text"]
        json_part = result[result.find("{") : result.rfind("}") + 1]
        data = json.loads(json_part)
        short = _truncate(data.get("short", description or title))
        fmt = data.get("format", _heuristic_format(title, description))
        if fmt not in ("Онлайн", "Оффлайн"):
            fmt = _heuristic_format(title, description)
        return short, fmt
    except Exception as e:
        print(f"[WARN] Ошибка генерации ({e}) — fallback.")
        return _truncate(description or title), _heuristic_format(title, description)
