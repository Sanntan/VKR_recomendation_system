from pathlib import Path
from scripts.database_mv.data_utils import preprocess_excel as preprocess_excel_func

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
    "Факультет",
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
    "Условия труда"
]

REQUIRED_COLS = ["Специальность", "Учебное заведение", "Учебный год", "ID участника проекта"]

def preprocess_excel(input_path: Path = INPUT_FILE, output_path: Path = OUTPUT_FILE):
    """Обертка над функцией preprocess_excel из data_utils с дефолтными параметрами."""
    return preprocess_excel_func(
        input_path=input_path,
        output_path=output_path,
        target_university=TARGET_UNIVERSITY,
        columns_to_keep=COLUMNS_TO_KEEP,
        required_cols=REQUIRED_COLS
    )

if __name__ == "__main__":
    preprocess_excel()
