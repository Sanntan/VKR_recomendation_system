import pandas as pd
from pathlib import Path

def load_excel(file_path: Path, header_row: int = None, required_cols: list[str] = None) -> pd.DataFrame:
    if not file_path.exists():
        raise FileNotFoundError(
            f"❌ Файл {file_path} не найден. Помести его в директорию sources."
        )
    
    def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Нормализует названия столбцов: убирает пробелы в начале и конце."""
        df.columns = df.columns.str.strip()
        return df
    
    # Если header_row указан явно, используем его
    if header_row is not None:
        df = pd.read_excel(file_path, header=header_row)
        return normalize_columns(df)
    
    # Если есть required_cols, пробуем найти правильный header_row
    if required_cols:
        # Сначала пробуем header_row=0 (A1)
        try:
            df = pd.read_excel(file_path, header=0)
            df = normalize_columns(df)
            missing_cols = [col for col in required_cols if col not in df.columns]
            if not missing_cols:
                print("✅ Заголовки найдены в строке 1 (A1)")
                return df
        except Exception:
            pass
        
        # Если не получилось, пробуем header_row=2 (B2, третья строка)
        try:
            df = pd.read_excel(file_path, header=2)
            df = normalize_columns(df)
            missing_cols = [col for col in required_cols if col not in df.columns]
            if not missing_cols:
                print("✅ Заголовки найдены в строке 3 (B2)")
                return df
        except Exception:
            pass
        
        # Если оба варианта не подошли, пробуем header_row=1 на всякий случай
        try:
            df = pd.read_excel(file_path, header=1)
            df = normalize_columns(df)
            missing_cols = [col for col in required_cols if col not in df.columns]
            if not missing_cols:
                print("✅ Заголовки найдены в строке 2")
                return df
        except Exception:
            pass
    
    # Если required_cols не указаны или ничего не подошло, используем дефолтный header_row=2
    df = pd.read_excel(file_path, header=2)
    return normalize_columns(df)

def validate_columns(df: pd.DataFrame, required_cols: list[str]) -> None:
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"❌ Не найдены обязательные столбцы: {missing_cols}")

def clean_and_filter(df: pd.DataFrame, target_university: str) -> pd.DataFrame:
    df = df[~df['Специальность'].astype(str).str.lower().str.contains('отсутствует', na=False)]
    df = df[df['Специальность'].notna() & (df['Специальность'].str.strip() != '')]
    df = df[df['Учебное заведение'].astype(str).str.strip() == target_university]
    return df

def keep_latest_records(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(by=["ID участника проекта", "Учебный год"], ascending=[True, False])
    df = df.drop_duplicates(subset=["ID участника проекта"], keep="first")
    return df

def save_to_excel(df: pd.DataFrame, output_file: Path) -> None:
    output_file.parent.mkdir(exist_ok=True)
    df.to_excel(output_file, index=False)
    print(f"✅ Файл сохранён: {output_file}")

def preprocess_excel(
    input_path: Path,
    output_path: Path,
    target_university: str,
    columns_to_keep: list[str],
    required_cols: list[str]
) -> pd.DataFrame:
    """
    Предобрабатывает Excel файл: загружает, валидирует, фильтрует и сохраняет.
    
    Args:
        input_path: Путь к исходному Excel файлу
        output_path: Путь для сохранения обработанного файла
        target_university: Целевое учебное заведение для фильтрации
        columns_to_keep: Список столбцов для сохранения
        required_cols: Список обязательных столбцов для валидации
    
    Returns:
        Обработанный DataFrame
    """
    df = load_excel(input_path, required_cols=required_cols)
    validate_columns(df, required_cols)
    df = clean_and_filter(df, target_university)
    df = keep_latest_records(df)
    
    # Нормализуем названия столбцов (на всякий случай)
    df.columns = df.columns.str.strip()
    
    # Находим столбцы из columns_to_keep, которые есть в файле
    available_from_list = [col for col in columns_to_keep if col in df.columns]
    missing_from_list = [col for col in columns_to_keep if col not in df.columns]
    
    # Если после "Пассивный словарный запас" в файле есть дополнительные столбцы,
    # автоматически добавляем их все
    cols_to_save = available_from_list.copy()
    
    if "Пассивный словарный запас" in df.columns:
        passive_vocab_idx = list(df.columns).index("Пассивный словарный запас")
        # Находим все столбцы после "Пассивный словарный запас" в исходном файле
        cols_after_passive = list(df.columns[passive_vocab_idx + 1:])
        
        # Добавляем все столбцы после "Пассивный словарный запас", которых еще нет в списке
        for col in cols_after_passive:
            if col not in cols_to_save:
                cols_to_save.append(col)
                print(f"✅ Автоматически добавлен столбец после 'Пассивный словарный запас': {col}")
    
    # Формируем итоговый список столбцов в правильном порядке:
    # 1. Все столбцы из columns_to_keep в том порядке, в котором они указаны (если они есть в файле)
    # 2. Все остальные столбцы после "Пассивный словарный запас" в том порядке, в котором они идут в файле
    ordered_cols = []
    
    # Сначала добавляем столбцы из columns_to_keep до "Пассивный словарный запас" включительно
    for col in columns_to_keep:
        if col in cols_to_save and col not in ordered_cols:
            ordered_cols.append(col)
    
    # Затем добавляем все столбцы после "Пассивный словарный запас", которые есть в файле
    if "Пассивный словарный запас" in df.columns:
        passive_idx = list(df.columns).index("Пассивный словарный запас")
        cols_after = list(df.columns[passive_idx + 1:])
        for col in cols_after:
            if col not in ordered_cols:
                ordered_cols.append(col)
    
    # Если есть столбцы из columns_to_keep, которых не нашли, выводим предупреждение
    if missing_from_list:
        print(f"\n⚠️ Предупреждение: следующие столбцы из списка не найдены в файле:")
        for col in missing_from_list:
            print(f"   - {col}")
    
    print(f"\n✅ Сохраняем {len(ordered_cols)} столбцов (из них {len(available_from_list)} из запрошенного списка)")
    
    # Сохраняем DataFrame с выбранными столбцами
    df = df[ordered_cols]
    save_to_excel(df, output_path)
    return df
