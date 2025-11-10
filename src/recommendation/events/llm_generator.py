# -*- coding: utf-8 -*-
import torch
import pandas as pd
import numpy as np
from unsloth import FastLanguageModel
from sentence_transformers import SentenceTransformer
from src.recommendation.events.utils import format_event_for_db

# === Проверка и инициализация GPU ===
if not torch.cuda.is_available():
    raise RuntimeError("❌ GPU не обнаружена. Проверь, что установлены CUDA и драйверы NVIDIA.")

device = torch.device("cuda")
print(f"✅ Используется устройство: {torch.cuda.get_device_name(0)}")

# === Инициализация моделей ===
model_name = "unsloth/Qwen3-4B-Instruct-2507"
print("Загрузка модели Qwen3-4B-Instruct с поддержкой GPU...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_name,
    max_seq_length=2048,
    load_in_4bit=False,   # True - экономия VRAM, False - полный размер
    load_in_8bit=False,
)
model.to(device)
print("✅ Модель успешно загружена на GPU")

embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
embedder.to(device)
print("✅ Sentence-BERT загружен на GPU")

# === Основные функции ===

def load_events_csv(filepath: str):
    """
    Загружает события из CSV, превращая их в список словарей.
    """
    df = pd.read_csv(filepath)
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")


def generate_short_description(event_info: str) -> str:
    """
    Генерирует краткое описание мероприятия для Telegram-канала на основе event_info.
    """
    system_prompt = """
Ты — ассистент, который преобразует информацию о мероприятиях университета в структурированное описание для Telegram-канала.
Формат вывода:
<2 предложения без заголовка>
Подойдёт тем, кто <описание аудитории>
Правила:
- Только русский язык
- Без приглашений и технических деталей
- Не копируй текст, переформулируй
- Кратко, спокойно, формально
    """
    messages = [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": event_info.strip()},
    ]
    input_ids = tokenizer.apply_chat_template(
        messages, tokenize=True, return_tensors="pt", add_generation_prompt=True
    ).to(device)
    output = model.generate(input_ids=input_ids, max_new_tokens=350, temperature=0.2, top_p=0.9)
    result = tokenizer.decode(output[0], skip_special_tokens=True)
    # Если генерация содержит "assistant", удаляем его
    if "assistant" in result.lower():
        result = result.split("assistant")[-1].strip()
    return result.strip()


def extract_event_dates(event_text: str) -> str:
    """
    Извлекает из текста даты проведения мероприятия в формате:
    start_date = DD.MM.YYYY HH:MM
    end_date = DD.MM.YYYY HH:MM
    """
    system_prompt = """
Ты — ассистент, который извлекает даты проведения мероприятия из текста.
Формат:
start_date = DD.MM.YYYY HH:MM
end_date = DD.MM.YYYY HH:MM
    """.strip()
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": event_text}]
    input_ids = tokenizer.apply_chat_template(messages, tokenize=True, return_tensors="pt", add_generation_prompt=True).to(device)
    output = model.generate(input_ids=input_ids, max_new_tokens=80, temperature=0.1, top_p=0.9)
    result = tokenizer.decode(output[0], skip_special_tokens=True).strip()
    if "assistant" in result.lower():
        result = result.split("assistant")[-1].strip()
    return result


def detect_event_online(event_text: str) -> str:
    """
    Определяет формат мероприятия: онлайн, офлайн или не определено.
    Возвращает:
    online = True
    online = False
    online = None
    """
    system_prompt = """
Ты — ассистент, который определяет формат мероприятия: онлайн или офлайн.
Формат:
online = True
online = False
online = None
    """.strip()
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": event_text.strip()}]
    input_ids = tokenizer.apply_chat_template(messages, tokenize=True, return_tensors="pt", add_generation_prompt=True).to(device)
    output = model.generate(input_ids=input_ids, max_new_tokens=30, temperature=0.1, top_p=0.9)
    result = tokenizer.decode(output[0], skip_special_tokens=True).strip()
    if "assistant" in result.lower():
        result = result.split("assistant")[-1].strip()
    return result


def format_event_for_model(event: dict) -> str:
    """
    Форматирует словарь мероприятия в текст для LLM.
    """
    return f"""
Title: {event.get('title', '')}
Description: {event.get('description', '')}
Start date: {event.get('start_date')}
End date: {event.get('end_date')}
Link: {event.get('link', '')}
Format raw: {"Online" if event.get('online') else "Offline" if event.get('online') is not None else "Unknown"}
"""


def format_event_for_date_model(event: dict) -> str:
    """
    Форматирует мероприятие для уточнения или извлечения дат для LLM.
    """
    return f"""
Title: {event.get('title', '').strip()}
Description: {event.get('description', '').strip()}
Existing start date: {event.get('start_date')}
Existing end date: {event.get('end_date')}
""".strip()


def format_event_for_online_model(event: dict) -> str:
    """
    Форматирует мероприятие для уточнения онлайн/оффлайн для LLM.
    """
    return f"""
Title: {event.get('title', '').strip()}
Description: {event.get('description', '').strip()}
Existing online flag: {event.get('online')}
""".strip()


def vectorize_short_description(short_description: str):
    """
    Векторизует краткое описание (sentence embedding).
    """
    if not short_description or not short_description.strip():
        return None
    embedding = embedder.encode([short_description])[0]
    return np.array(embedding, dtype=float)


def process_events(events, limit=5):
    """
    Полностью обрабатывает события: генерирует короткое описание, определяет формат,
    извлекает даты, создает эмбеддинги и формирует полный объект события по структуре БД.
    
    Аргументы:
      events: список мероприятий (dict) с полями: title, link, description, 
              start_date, end_date, image
      limit: ограничение по числу обрабатываемых событий
    
    Возвращает:
      List[dict] с полями согласно структуре Events в БД:
      - title, short_description, description, format, start_date, end_date,
        link, image_url, vector_embedding
    """
    processed = []
    total = len(events) if limit is None else min(len(events), limit)
    
    print(f"🚀 Начало обработки {total} мероприятий...")
    
    for i, event in enumerate(events[:total]):
        try:
            # Форматируем событие для LLM
            info = format_event_for_model(event)
            desc_date = format_event_for_date_model(event)
            desc_online = format_event_for_online_model(event)

            # Генерируем короткое описание
            short_description = generate_short_description(info)
            
            # Извлекаем/уточняем даты
            if not event.get("start_date") or not event.get("end_date"):
                event_dates = extract_event_dates(desc_date)
            else:
                event_dates = f"start_date = {event['start_date']}\nend_date = {event['end_date']}"
            
            # Определяем формат (онлайн/офлайн)
            if event.get("online") in [None, "", "None"]:
                event_online = detect_event_online(desc_online)
            else:
                event_online = f"online = {event['online']}"
            
            # Векторизуем короткое описание
            vector = vectorize_short_description(short_description)
            
            # Объединяем исходные данные с обработанными
            event_processed = {
                **event,  # Исходные поля: title, link, description, start_date, end_date, image
                "short_description": short_description,
                "dates_extracted_raw": event_dates,
                "online_extracted_raw": event_online,
                "embedding": vector.tolist() if vector is not None else None,
            }
            
            # Форматируем для БД
            event_for_db = format_event_for_db(event_processed)
            
            processed.append(event_for_db)
            print(f"[{i+1}/{total}] ✅ Обработано: {event.get('title', 'Без названия')}")
            
        except Exception as e:
            print(f"[{i+1}/{total}] ❌ Ошибка при обработке '{event.get('title', 'Без названия')}': {e}")
            # Добавляем событие с базовыми данными даже при ошибке
            event_for_db = format_event_for_db(event)
            processed.append(event_for_db)
    
    print(f"\n✅ Обработка завершена. Обработано {len(processed)} мероприятий.")
    return processed
