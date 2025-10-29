import pandas as pd
from pathlib import Path

# === Пути ===
BASE_DIR = Path(__file__).resolve().parent        # /scripts
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

input_file = BASE_DIR / "123.xlsx"
output_file = RESULTS_DIR / "filtered_data.xlsx"

# === Константы ===
target_university = 'ФГАОУ ВО "ТЮМЕНСКИЙ ГОСУДАРСТВЕННЫЙ УНИВЕРСИТЕТ" (ТюмГУ)'

columns_to_keep = [
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

# === Загрузка Excel ===
try:
    # Пропускаем первые две строки, если таблица начинается с 3-й
    df = pd.read_excel(input_file, header=2)
except FileNotFoundError:
    raise FileNotFoundError(f"❌ Файл {input_file} не найден. Помести его в папку scripts.")

# === Проверка, что нужные столбцы существуют ===
missing_cols = [col for col in ["Специальность", "Учебное заведение"] if col not in df.columns]
if missing_cols:
    raise ValueError(f"❌ В файле не найдены обязательные столбцы: {missing_cols}. "
                     f"Проверь, что таблица начинается с правильной строки (например, header=2).")

# === Очистка строк ===
df = df[~df['Специальность'].astype(str).str.lower().str.contains('отсутствует', na=False)]
df = df[df['Специальность'].notna() & (df['Специальность'].str.strip() != '')]
df = df[df['Учебное заведение'].astype(str).str.strip() == target_university]

# === Фильтрация столбцов ===
df = df[[col for col in columns_to_keep if col in df.columns]]

# === Сохранение результата ===
df.to_excel(output_file, index=False)
print(f"✅ Фильтрация завершена.\nРезультат сохранён: {output_file}")
