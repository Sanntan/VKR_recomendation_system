#!/usr/bin/env python3
"""
Скрипт для предобработки Excel файла студентов.

Выполняет:
1. Загрузку исходного Excel файла
2. Фильтрацию по учебному заведению (оставляет только ТюмГУ)
3. Оставление только нужных столбцов (ID участника, Специальность, Учебное заведение, компетенции)
4. Сохранение обработанного файла
"""

import sys
from pathlib import Path
import pandas as pd

# Добавляем корень проекта в путь для импортов
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.database_mv.helpers.data_utils import load_excel
from scripts.database_mv.helpers.process_students import COMPETENCY_COLUMNS, REQUIRED_COLS

# Пути к файлам
BASE_DIR = Path(__file__).resolve().parent
SOURCES_DIR = BASE_DIR / "sources" / "students"
RESULTS_DIR = BASE_DIR / "results" / "students"

INPUT_FILE = SOURCES_DIR / "123.xlsx"
OUTPUT_FILE = RESULTS_DIR / "123.xlsx"

# Целевое учебное заведение
TARGET_INSTITUTION = 'ФГАОУ ВО "ТЮМЕНСКИЙ ГОСУДАРСТВЕННЫЙ УНИВЕРСИТЕТ" (ТюмГУ)'

# Столбцы, которые нужно оставить
COLUMNS_TO_KEEP = ["ID участника проекта", "Специальность", "Учебное заведение"] + COMPETENCY_COLUMNS


def preprocess_students_excel(
    input_path: Path | str = None,
    output_path: Path | str = None,
) -> None:
    """
    Предобрабатывает Excel файл студентов:
    - Фильтрует по учебному заведению
    - Оставляет только нужные столбцы
    - Сохраняет результат
    
    Args:
        input_path: Путь к входному Excel файлу (по умолчанию INPUT_FILE)
        output_path: Путь для сохранения обработанного файла (по умолчанию OUTPUT_FILE)
    """
    input_path = Path(input_path) if input_path else INPUT_FILE
    output_path = Path(output_path) if output_path else OUTPUT_FILE
    
    print("=" * 80)
    print("ПРЕДОБРАБОТКА EXCEL ФАЙЛА СТУДЕНТОВ")
    print("=" * 80)
    
    # Проверяем наличие входного файла
    if not input_path.exists():
        raise FileNotFoundError(
            f"❌ Файл {input_path} не найден. Поместите Excel файл в директорию {SOURCES_DIR}"
        )
    
    print(f"\n📂 Загрузка данных из: {input_path}")
    
    # Пробуем разные варианты header для определения правильной строки заголовков
    print("   🔍 Поиск строки с заголовками...")
    df = None
    header_row = None
    
    # Сначала читаем первые 10 строк без заголовков для анализа
    print("   🔍 Анализ структуры файла...")
    raw_data = pd.read_excel(input_path, header=None, nrows=10)
    
    # Ищем строку, которая содержит "Учебное заведение" или "ID участника проекта"
    target_header_row = None
    for row_idx in range(min(10, len(raw_data))):
        row_values = [str(val).strip().lower() if pd.notna(val) else "" for val in raw_data.iloc[row_idx]]
        if any("учебное заведение" in val for val in row_values) or any("id участника проекта" in val for val in row_values):
            target_header_row = row_idx
            print(f"   ✅ Найдена строка с заголовками: строка {row_idx + 1}")
            break
    
    # Если нашли строку с заголовками, используем её
    if target_header_row is not None:
        try:
            df = pd.read_excel(input_path, header=target_header_row)
            df.columns = df.columns.str.strip()
            header_row = target_header_row
            print(f"   ✅ Загружено с header={target_header_row}")
        except Exception as e:
            print(f"   ⚠️  Ошибка при загрузке с header={target_header_row}: {e}")
    
    # Если не нашли, пробуем стандартные варианты
    if df is None:
        for test_header in [0, 1, 2]:
            try:
                test_df = pd.read_excel(input_path, header=test_header)
                test_df.columns = test_df.columns.str.strip()
                
                # Проверяем наличие ключевых столбцов
                has_participant_id = "ID участника проекта" in test_df.columns
                has_specialty = "Специальность" in test_df.columns
                has_institution = "Учебное заведение" in test_df.columns
                
                if has_participant_id and (has_specialty or has_institution):
                    df = test_df
                    header_row = test_header
                    print(f"   ✅ Заголовки найдены в строке {test_header + 1} (header={test_header})")
                    break
            except Exception as e:
                continue
    
    # Если все еще не нашли, пробуем использовать load_excel
    if df is None:
        try:
            print("   🔍 Используем функцию load_excel...")
            df = load_excel(input_path, required_cols=None)
        except Exception as e:
            print(f"   ⚠️  load_excel не сработал: {e}")
            # Последняя попытка - читаем с header=0
            df = pd.read_excel(input_path, header=0)
            df.columns = df.columns.str.strip()
    
    print(f"✅ Загружено строк: {len(df)}")
    print(f"   Столбцов: {len(df.columns)}")
    
    # Проверяем наличие столбца "Учебное заведение"
    if "Учебное заведение" not in df.columns:
        print(f"⚠️  Столбец 'Учебное заведение' не найден в заголовках!")
        print(f"   Доступные столбцы (первые 15): {list(df.columns[:15])}")
        
        # Пробуем найти похожий столбец в заголовках
        possible_cols = [col for col in df.columns if "учебное" in str(col).lower() or "заведение" in str(col).lower()]
        if possible_cols:
            print(f"   🔍 Найдены похожие столбцы: {possible_cols}")
            # Используем первый найденный
            df = df.rename(columns={possible_cols[0]: "Учебное заведение"})
            print(f"   ✅ Переименован столбец '{possible_cols[0]}' в 'Учебное заведение'")
        else:
            # Ищем столбец, где в данных есть "ФГАОУ ВО" или "ТЮМЕНСКИЙ ГОСУДАРСТВЕННЫЙ"
            print("   🔍 Ищем столбец по содержимому (ищем 'ФГАОУ ВО' или 'ТЮМЕНСКИЙ')...")
            for col in df.columns:
                # Проверяем первые несколько значений в столбце
                sample_values = df[col].head(10).astype(str).str.lower()
                if any("фгаоу во" in val or "тюменский государственный" in val for val in sample_values):
                    print(f"   ✅ Найден столбец с учебными заведениями: '{col}'")
                    df = df.rename(columns={col: "Учебное заведение"})
                    break
            
            if "Учебное заведение" not in df.columns:
                raise ValueError(
                    "Столбец 'Учебное заведение' обязателен для фильтрации и не найден в файле.\n"
                    f"Проверьте, что файл содержит столбец с названиями учебных заведений."
                )
    
    # Фильтрация по учебному заведению
    print(f"\n🔍 Фильтрация по учебному заведению...")
    print(f"   Целевое заведение: {TARGET_INSTITUTION}")
    
    initial_count = len(df)
    
    # Нормализуем значения для сравнения (убираем лишние пробелы, приводим к строке)
    df["Учебное заведение"] = df["Учебное заведение"].astype(str).str.strip()
    
    # Фильтруем: оставляем только строки, где учебное заведение точно совпадает с целевым
    df_filtered = df[df["Учебное заведение"] == TARGET_INSTITUTION].copy()
    
    filtered_count = len(df_filtered)
    removed_count = initial_count - filtered_count
    
    print(f"   📊 Исходное количество строк: {initial_count}")
    print(f"   ✅ Осталось после фильтрации: {filtered_count}")
    print(f"   ❌ Удалено строк: {removed_count}")
    
    if filtered_count == 0:
        print(f"\n❌ После фильтрации не осталось ни одной строки!")
        print(f"   Проверьте, что в файле есть строки с учебным заведением: {TARGET_INSTITUTION}")
        return
    
    # Проверяем наличие обязательных столбцов
    print(f"\n📋 Проверка наличия столбцов...")
    missing_cols = []
    available_cols = []
    
    for col in COLUMNS_TO_KEEP:
        if col in df_filtered.columns:
            available_cols.append(col)
        else:
            missing_cols.append(col)
    
    if missing_cols:
        print(f"   ⚠️  Не найдены столбцы: {missing_cols}")
        print(f"   Будет использовано только {len(available_cols)} из {len(COLUMNS_TO_KEEP)} столбцов")
    
    # Оставляем только нужные столбцы (те, которые есть в файле)
    columns_to_keep_final = [col for col in COLUMNS_TO_KEEP if col in df_filtered.columns]
    
    if not columns_to_keep_final:
        raise ValueError("❌ Не найдено ни одного нужного столбца в файле!")
    
    df_final = df_filtered[columns_to_keep_final].copy()
    
    print(f"   ✅ Оставлено столбцов: {len(columns_to_keep_final)}")
    print(f"   Столбцы: {', '.join(columns_to_keep_final[:5])}...")
    
    # Сохраняем результат
    print(f"\n💾 Сохранение результата в: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df_final.to_excel(output_path, index=False)
    
    print(f"✅ Файл сохранён: {output_path}")
    
    print(f"\n✅ Предобработка завершена успешно!")
    print(f"   📊 Итоговая статистика:")
    print(f"      - Строк в исходном файле: {initial_count}")
    print(f"      - Строк после фильтрации: {filtered_count}")
    print(f"      - Удалено строк: {removed_count}")
    print(f"      - Столбцов в результате: {len(columns_to_keep_final)}")
    print(f"   📁 Результат сохранён в: {output_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Предобработка Excel файла студентов: фильтрация по учебному заведению и выбор столбцов"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help=f"Путь к входному Excel файлу (по умолчанию: {INPUT_FILE})"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help=f"Путь для сохранения обработанного файла (по умолчанию: {OUTPUT_FILE})"
    )
    
    args = parser.parse_args()
    
    try:
        preprocess_students_excel(
            input_path=args.input,
            output_path=args.output
        )
    except Exception as e:
        print(f"\n❌ Ошибка выполнения: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

