"""Утилиты для обработки студентов: обработка Excel, генерация профилей, загрузка в БД."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Any
import pandas as pd

from scripts.database_mv.helpers.data_utils import load_excel
from src.recommendation.students.profile_generator import (
    generate_profile_description,
    vectorize_profiles_batch,
)

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


def process_students_from_excel(
    input_path: Path | str,
    output_path: Path | str,
) -> list[dict[str, Any]]:
    """
    Обрабатывает данные студентов из Excel файла и сохраняет результаты в JSON.
    
    Args:
        input_path: Путь к входному Excel файлу
        output_path: Путь для сохранения JSON файла с результатами
    
    Returns:
        Список словарей с данными студентов (ID участника проекта, Описание компетенций, Вектор)
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    print("=" * 80)
    print("ОБРАБОТКА ДАННЫХ СТУДЕНТОВ")
    print("=" * 80)
    
    # Проверяем наличие входного файла
    if not input_path.exists():
        raise FileNotFoundError(
            f"❌ Файл {input_path} не найден. Поместите Excel файл в директорию sources/students"
        )
    
    print(f"\n📂 Загрузка данных из: {input_path}")
    
    # Загружаем Excel файл
    df = load_excel(input_path, required_cols=REQUIRED_COLS)
    
    print(f"✅ Загружено строк: {len(df)}")
    
    # Проверяем наличие обязательных столбцов
    missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"❌ Не найдены обязательные столбцы: {missing_cols}")
    
    # Фильтрация по учебному заведению
    target_institution = 'ФГАОУ ВО "ТЮМЕНСКИЙ ГОСУДАРСТВЕННЫЙ УНИВЕРСИТЕТ" (ТюмГУ)'
    if "Учебное заведение" in df.columns:
        initial_count = len(df)
        # Нормализуем значения для сравнения (убираем лишние пробелы, приводим к строке)
        df["Учебное заведение"] = df["Учебное заведение"].astype(str).str.strip()
        # Фильтруем: оставляем только строки, где учебное заведение точно совпадает с целевым
        df = df[df["Учебное заведение"] == target_institution]
        filtered_count = len(df)
        removed_count = initial_count - filtered_count
        if removed_count > 0:
            print(f"🔍 Фильтрация по учебному заведению: удалено {removed_count} строк (осталось {filtered_count})")
        else:
            print(f"🔍 Фильтрация по учебному заведению: все строки соответствуют '{target_institution}'")
    else:
        print(f"⚠️  Столбец 'Учебное заведение' не найден, фильтрация пропущена")
    
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
                "Специальность": specialty_str,
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
        return []
    
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
        raise
    
    # Этап 3: Формирование результатов
    print(f"\n📋 Этап 3: Формирование результатов...")
    
    results = []
    for i, student_info in enumerate(student_data):
        try:
            # Преобразуем numpy array в список для JSON
            vector_list = embeddings[i].tolist()
            
            results.append({
                "ID участника проекта": student_info["ID участника проекта"],
                "Специальность": student_info["Специальность"],
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
        return []
    
    # Сохраняем результаты в JSON файл
    print(f"\n💾 Сохранение результатов в: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Файл сохранён: {output_path}")
    
    print(f"\n✅ Обработка завершена успешно!")
    print(f"   Результаты сохранены в: {output_path}")
    print(f"   Всего записей: {len(results)}")
    print(f"   Формат: JSON с полями: ID участника проекта, Специальность, Описание компетенций, Вектор")
    
    return results


def load_students_from_json_file(json_path: Path | str) -> list[dict[str, Any]]:
    """Загружает студентов из указанного JSON-файла."""
    json_path = Path(json_path)
    
    if not json_path.exists():
        print(f"❌ Файл {json_path} не найден!")
        return []
    
    try:
        with json_path.open("r", encoding="utf-8") as f:
            students = json.load(f)
        print(f"✅ Загружено {len(students)} студентов из {json_path}")
        return students
    except (json.JSONDecodeError, Exception) as exc:
        print(f"❌ Ошибка загрузки файла {json_path}: {exc}")
        raise


def insert_students_to_db(
    students: list[dict[str, Any]],
    default_institution: str = "Университет",
    batch_size: int = 100,
    limit: int | None = None,
) -> tuple[int, int]:
    """
    Добавляет студентов в БД, пропуская дубликаты.
    Оптимизированная версия с batch insert и предварительной загрузкой данных.
    
    Args:
        students: список словарей с данными студентов
        default_institution: название учебного заведения по умолчанию
        batch_size: размер батча для вставки
        limit: максимальное количество студентов для добавления (None = без ограничений)
    
    Returns:
        кортеж (добавлено, пропущено)
    """
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from src.core.database.connection import engine
    from src.core.database.models import Students, Directions
    
    added_count = 0
    skipped_count = 0
    
    with Session(engine) as db:
        # Применяем лимит, если указан (создаем новый список, чтобы не изменять оригинал)
        original_count = len(students)
        if limit is not None and limit > 0:
            students = list(students[:limit])
            print(f"\n📊 Подготовка к вставке {len(students)} студентов из {original_count} (лимит: {limit})...")
        else:
            print(f"\n📊 Подготовка к вставке {len(students)} студентов...")
        
        # Предварительно загружаем все существующие participant_id одним запросом
        print("   🔍 Проверка существующих студентов...")
        existing_participant_ids = set()
        existing_students = db.execute(select(Students.participant_id)).scalars().all()
        existing_participant_ids.update(existing_students)
        print(f"   ✅ Найдено существующих студентов: {len(existing_participant_ids)}")
        
        # Предварительно загружаем все направления в словарь для быстрого поиска
        print("   🔍 Загрузка направлений...")
        directions_map = {}
        all_directions = db.execute(select(Directions)).scalars().all()
        for direction in all_directions:
            directions_map[direction.title.lower().strip()] = direction.id
        print(f"   ✅ Загружено направлений: {len(directions_map)}")
        
        # Подготавливаем данные для batch insert
        students_to_insert = []
        
        print(f"\n🔄 Обработка студентов...")
        for i, student_data in enumerate(students, 1):
            try:
                participant_id = student_data.get("ID участника проекта")
                if not participant_id:
                    skipped_count += 1
                    continue
                
                participant_id = str(participant_id).strip()
                
                # Проверяем, существует ли студент
                if participant_id in existing_participant_ids:
                    skipped_count += 1
                    if skipped_count <= 5 or skipped_count % 100 == 0:
                        print(f"   ⏭️  Пропущено (дубликат): {participant_id}")
                    continue
                
                # Получаем направление по специальности
                specialty = student_data.get("Специальность")
                direction_id = None
                if specialty:
                    specialty_key = str(specialty).strip().lower()
                    direction_id = directions_map.get(specialty_key)
                    if not direction_id:
                        # Пробуем найти без учета регистра через ilike (если не нашли в кэше)
                        from src.core.database.crud.directions import get_direction_by_title
                        direction = get_direction_by_title(db, specialty)
                        if direction:
                            direction_id = direction.id
                            # Добавляем в кэш для следующих итераций
                            directions_map[specialty_key] = direction_id
                
                # Получаем вектор профиля
                profile_embedding = student_data.get("Вектор")
                if not profile_embedding:
                    skipped_count += 1
                    continue
                
                # Подготавливаем данные для вставки
                student_dict = {
                    "participant_id": participant_id,
                    "institution": default_institution,
                    "direction_id": direction_id,
                    "profile_embedding": profile_embedding,
                }
                students_to_insert.append(student_dict)
                existing_participant_ids.add(participant_id)  # Добавляем в set, чтобы избежать дубликатов в батче
                
                # Вставляем батчами
                if len(students_to_insert) >= batch_size:
                    try:
                        db.bulk_insert_mappings(Students, students_to_insert)
                        db.commit()
                        added_count += len(students_to_insert)
                        print(f"   ✅ Вставлено батч: {len(students_to_insert)} студентов (всего: {added_count})")
                        students_to_insert = []
                    except Exception as e:
                        db.rollback()
                        print(f"   ❌ Ошибка при batch insert: {e}")
                        # Пробуем вставить по одному из этого батча
                        for student_dict_single in students_to_insert:
                            try:
                                db.bulk_insert_mappings(Students, [student_dict_single])
                                db.commit()
                                added_count += 1
                            except Exception:
                                db.rollback()
                                skipped_count += 1
                        students_to_insert = []
                
            except Exception as e:
                print(f"   ❌ Ошибка при обработке студента {student_data.get('ID участника проекта', 'неизвестно')}: {e}")
                skipped_count += 1
        
        # Вставляем оставшиеся студенты
        if students_to_insert:
            try:
                db.bulk_insert_mappings(Students, students_to_insert)
                db.commit()
                added_count += len(students_to_insert)
                print(f"   ✅ Вставлено финальный батч: {len(students_to_insert)} студентов (всего: {added_count})")
            except Exception as e:
                db.rollback()
                print(f"   ❌ Ошибка при финальном batch insert: {e}")
                # Пробуем вставить по одному
                for student_dict_single in students_to_insert:
                    try:
                        db.bulk_insert_mappings(Students, [student_dict_single])
                        db.commit()
                        added_count += 1
                    except Exception:
                        db.rollback()
                        skipped_count += 1
    
    print(f"\n📊 Итоговая статистика:")
    print(f"   ✅ Добавлено: {added_count}")
    print(f"   ⏭️  Пропущено: {skipped_count}")
    
    return added_count, skipped_count

