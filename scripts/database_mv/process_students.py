#!/usr/bin/env python3
"""
Скрипт для обработки данных студентов из Excel файла.

Читает данные о студентах из Excel файла, генерирует текстовое описание компетенций
и вектор профиля для каждого студента, сохраняет результаты в JSON файл.
"""

import sys
import json
from pathlib import Path
import pandas as pd
from typing import Dict, Optional

# Добавляем корень проекта в путь для импортов
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.recommendation.students.profile_generator import (
    generate_profile_description,
    vectorize_profiles_batch,
    COMPETENCIES
)
from scripts.database_mv.helpers.data_utils import load_excel


# Пути к файлам
BASE_DIR = Path(__file__).resolve().parent
SOURCES_DIR = BASE_DIR / "sources" / "students"
RESULTS_DIR = BASE_DIR / "results" / "students"

INPUT_FILE = SOURCES_DIR / "123.xlsx"
OUTPUT_FILE = RESULTS_DIR / "students_profiles.json"

# Список всех компетенций (28 компетенций)
# Порядок соответствует порядку в Excel файле
COMPETENCY_COLUMNS = [
    "Анализ информации",
    "Планирование",
    "Ориентация на результат",
    "Стрессоустойчивость",
    "Партнерство/Сотрудничество",
    "Следование правилам и процедурам",
    "Саморазвитие",
    "Лидерство",
    "Эмоциональный интеллект",
    "Клиентоориентированность",
    "Коммуникация",
    "Пассивный словарный запас",
    "Автономия",
    "Альтруизм",
    "Вызов",
    "Заработок",
    "Карьера",
    "Креативность",
    "Отношения",
    "Признание",
    "Принадлежность",
    "Саморазвитие.1",
    "Смысл",
    "Сотрудничество",
    "Стабильность",
    "Традиция",
    "Управление",
    "Условия труда",
]

# Обязательные столбцы для валидации
REQUIRED_COLS = ["ID участника проекта", "Специальность"] + COMPETENCY_COLUMNS


def normalize_competency_value(value) -> Optional[int]:
    """
    Нормализует значение компетенции из Excel.
    Обрабатывает пропущенные значения, NaN, строки и числа.
    
    Args:
        value: Значение из Excel (может быть int, float, str, None, NaN)
    
    Returns:
        Нормализованное значение (int от 200 до 800) или None, если значение пропущено
    """
    # Обрабатываем NaN и None
    if pd.isna(value) or value is None:
        return None
    
    # Обрабатываем строки
    if isinstance(value, str):
        value = value.strip()
        if value in ("-", "", "None", "null", "nan", "NaN"):
            return None
        try:
            score = float(value)
        except (ValueError, TypeError):
            return None
    else:
        try:
            score = float(value)
        except (ValueError, TypeError):
            return None
    
    # Проверяем валидность диапазона (200-800)
    if 200 <= score <= 800:
        return int(round(score))
    else:
        return None


def extract_competencies(row: pd.Series) -> Dict[str, int]:
    """
    Извлекает компетенции из строки DataFrame.
    
    Args:
        row: Строка DataFrame с данными студента
    
    Returns:
        Словарь {название_компетенции: т-балл} с валидными компетенциями
    """
    competencies = {}
    
    for competency_name in COMPETENCY_COLUMNS:
        if competency_name not in row.index:
            continue
        
        value = row[competency_name]
        normalized_value = normalize_competency_value(value)
        
        if normalized_value is not None:
            competencies[competency_name] = normalized_value
    
    return competencies


def process_students() -> None:
    """
    Обрабатывает данные студентов из Excel файла и сохраняет результаты.
    """
    print("=" * 80)
    print("ОБРАБОТКА ДАННЫХ СТУДЕНТОВ")
    print("=" * 80)
    
    # Проверяем наличие входного файла
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"❌ Файл {INPUT_FILE} не найден. Поместите Excel файл в директорию {SOURCES_DIR}"
        )
    
    print(f"\n📂 Загрузка данных из: {INPUT_FILE}")
    
    # Загружаем Excel файл
    df = load_excel(INPUT_FILE, required_cols=REQUIRED_COLS)
    
    print(f"✅ Загружено строк: {len(df)}")
    
    # Проверяем наличие обязательных столбцов
    missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"❌ Не найдены обязательные столбцы: {missing_cols}")
    
    # Этап 1: Подготовка данных и генерация текстовых описаний
    print(f"\n🔄 Этап 1: Подготовка данных и генерация текстовых описаний...")
    
    student_data = []
    skipped_count = 0
    
    for idx, row in df.iterrows():
        participant_id = row.get("ID участника проекта")
        specialty = row.get("Специальность")
        
        # Пропускаем строки без ID участника
        if pd.isna(participant_id) or participant_id is None:
            skipped_count += 1
            continue
        
        # Преобразуем ID в строку
        participant_id = str(participant_id).strip()
        
        # Извлекаем компетенции
        competencies = extract_competencies(row)
        
        # Пропускаем студентов без валидных компетенций
        if not competencies:
            skipped_count += 1
            continue
        
        # Преобразуем специальность в строку (если есть)
        specialty_str = None
        if not pd.isna(specialty) and specialty is not None:
            specialty_str = str(specialty).strip()
            if specialty_str == "":
                specialty_str = None
        
        # Генерируем текстовое описание компетенций
        try:
            profile_description = generate_profile_description(specialty_str, competencies)
            student_data.append({
                "ID участника проекта": participant_id,
                "Описание компетенций": profile_description
            })
        except Exception as e:
            skipped_count += 1
            print(f"   ❌ Ошибка при генерации описания для студента {participant_id}: {e}")
            continue
    
    print(f"   ✅ Подготовлено {len(student_data)} студентов для векторизации")
    print(f"   ⏭️  Пропущено: {skipped_count} студентов")
    
    if not student_data:
        print("\n❌ Нет данных для обработки")
        return
    
    # Этап 2: Батчевая векторизация (оптимизировано)
    print(f"\n🧮 Этап 2: Батчевая векторизация профилей...")
    print(f"   Размер батча: 32")
    print(f"   Всего профилей для векторизации: {len(student_data)}")
    
    try:
        # Извлекаем все текстовые описания
        profile_texts = [item["Описание компетенций"] for item in student_data]
        
        # Векторизуем все профили батчами
        embeddings = vectorize_profiles_batch(
            profile_texts,
            batch_size=32,
            show_progress_bar=True
        )
        
        print(f"   ✅ Векторизация завершена: {len(embeddings)} векторов")
        
    except Exception as e:
        print(f"\n❌ Ошибка при батчевой векторизации: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Этап 3: Формирование результатов
    print(f"\n📋 Этап 3: Формирование результатов...")
    
    results = []
    for i, student_info in enumerate(student_data):
        try:
            # Преобразуем numpy array в список для JSON
            vector_list = embeddings[i].tolist()
            
            results.append({
                "ID участника проекта": student_info["ID участника проекта"],
                "Описание компетенций": student_info["Описание компетенций"],
                "Вектор": vector_list
            })
        except Exception as e:
            print(f"   ❌ Ошибка при формировании результата для студента {student_info['ID участника проекта']}: {e}")
            continue
    
    processed_count = len(results)
    
    print(f"\n📊 Статистика обработки:")
    print(f"   ✅ Успешно обработано: {processed_count} студентов")
    print(f"   ⏭️  Пропущено: {skipped_count} студентов")
    
    if not results:
        print("\n❌ Нет данных для сохранения")
        return
    
    # Сохраняем результаты в JSON файл
    print(f"\n💾 Сохранение результатов в: {OUTPUT_FILE}")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Файл сохранён: {OUTPUT_FILE}")
    
    print(f"\n✅ Обработка завершена успешно!")
    print(f"   Результаты сохранены в: {OUTPUT_FILE}")
    print(f"   Всего записей: {len(results)}")
    print(f"   Формат: JSON с полями: ID участника проекта, Описание компетенций, Вектор")


if __name__ == "__main__":
    try:
        process_students()
    except Exception as e:
        print(f"\n❌ Ошибка выполнения: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

