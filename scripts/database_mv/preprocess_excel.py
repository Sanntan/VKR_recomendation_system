from pathlib import Path
from scripts.database_mv.data_utils import (
    load_excel,
    validate_columns,
    clean_and_filter,
    keep_latest_records,
    save_to_excel
)

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"

INPUT_FILE = BASE_DIR / "123.xlsx"
OUTPUT_FILE = RESULTS_DIR / "filtered_data.xlsx"

TARGET_UNIVERSITY = 'ФГАОУ ВО "ТЮМЕНСКИЙ ГОСУДАРСТВЕННЫЙ УНИВЕРСИТЕТ" (ТюмГУ)'

COLUMNS_TO_KEEP = [
    "Учебный год",
    "ID участника проекта",
    "Учебное заведение",
    "Специальность",
    "Сводный отчёт",
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
    "Пассивный словарный запас"
]

REQUIRED_COLS = ["Специальность", "Учебное заведение", "Учебный год", "ID участника проекта"]

def preprocess_excel(input_path: Path = INPUT_FILE, output_path: Path = OUTPUT_FILE):
    df = load_excel(input_path)
    validate_columns(df, REQUIRED_COLS)
    df = clean_and_filter(df, TARGET_UNIVERSITY)
    df = keep_latest_records(df)
    df = df[[col for col in COLUMNS_TO_KEEP if col in df.columns]]
    save_to_excel(df, output_path)
    return df  # возвращаем DataFrame, чтобы можно было использовать дальше

if __name__ == "__main__":
    preprocess_excel()
