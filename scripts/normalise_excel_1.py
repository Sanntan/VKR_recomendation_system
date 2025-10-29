import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

input_file = BASE_DIR / "123.xlsx"
output_file = RESULTS_DIR / "filtered_data.xlsx"

target_university = 'ФГАОУ ВО "ТЮМЕНСКИЙ ГОСУДАРСТВЕННЫЙ УНИВЕРСИТЕТ" (ТюмГУ)'

columns_to_keep = [
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

try:
    df = pd.read_excel(input_file, header=2)
except FileNotFoundError:
    raise FileNotFoundError(f"❌ Файл {input_file} не найден. Помести его в папку scripts.")

missing_cols = [col for col in ["Специальность", "Учебное заведение", "Учебный год", "ID участника проекта"] if col not in df.columns]
if missing_cols:
    raise ValueError(f"❌ Не найдены обязательные столбцы: {missing_cols}")

# Очистка
df = df[~df['Специальность'].astype(str).str.lower().str.contains('отсутствует', na=False)]
df = df[df['Специальность'].notna() & (df['Специальность'].str.strip() != '')]
df = df[df['Учебное заведение'].astype(str).str.strip() == target_university]

# Фильтрация по самым свежим записям
# Сначала сортируем по году по убыванию, чтобы первая запись была самая актуальная
df = df.sort_values(by=["ID участника проекта", "Учебный год"], ascending=[True, False])

# Оставляем только одну запись для каждого ID
df = df.drop_duplicates(subset=["ID участника проекта"], keep="first")

# Фильтруем столбцы
df = df[[col for col in columns_to_keep if col in df.columns]]

df.to_excel(output_file, index=False)
print(f"✅ Фильтрация завершена.\nРезультат сохранён: {output_file}")
