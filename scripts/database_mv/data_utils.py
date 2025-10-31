import pandas as pd
from pathlib import Path

def load_excel(file_path: Path, header_row: int = 2) -> pd.DataFrame:
    if not file_path.exists():
        raise FileNotFoundError(f"❌ Файл {file_path} не найден. Помести его в папку scripts.")
    return pd.read_excel(file_path, header=header_row)

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
