import time
import csv
import os
import re
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException, TimeoutException

BASE_URL = "https://znanierussia.ru"
START_URL = "https://znanierussia.ru/events?dtStart=2025-10-01&status=offline&regionId=54049357-326d-4b8f-b224-3c6dc25d6dd3"
COMMON_CSV_FILE = "events.csv"


def setup_driver(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver_path = ChromeDriverManager().install()
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def normalize_link(href: str) -> str:
    """Нормализует ссылку до абсолютной."""
    if not href:
        return ""
    href = href.strip()
    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/"):
        href = BASE_URL.rstrip("/") + href
    elif not href.startswith("http"):
        href = BASE_URL.rstrip("/") + "/" + href
    return href


def get_event_links(start_url: str, driver: webdriver.Chrome = None, headless: bool = True,
                    wait_seconds: float = 2.5) -> List[str]:
    """Собирает ссылки на мероприятия, прокручивая страницу и нажимая 'Смотреть еще'.

    Args:
        start_url: URL страницы со списком мероприятий
        driver: Опциональный экземпляр WebDriver для переиспользования
        headless: Режим headless для создания нового драйвера (если driver не передан)
        wait_seconds: Время ожидания между действиями
    """
    should_close_driver = False
    if driver is None:
        driver = setup_driver(headless=headless)
        should_close_driver = True

    links: List[str] = []
    seen_links = set()

    try:
        driver.get(start_url)
        wait = WebDriverWait(driver, 10)
        time.sleep(3)  # Даём время на загрузку

        max_attempts = 50  # Максимальное количество нажатий на кнопку

        for attempt in range(max_attempts):
            print(f"[Znanie] Страница {attempt + 1}")

            # Собираем ссылки со страницы
            soup = BeautifulSoup(driver.page_source, "html.parser")
            event_items = soup.select("div.EventsList_listItem__UCayX")

            for item in event_items:
                link_elem = item.select_one("a[href*='/events/']")
                if link_elem:
                    href = link_elem.get("href", "")
                    normalized = normalize_link(href)
                    if normalized and normalized not in seen_links:
                        seen_links.add(normalized)
                        links.append(normalized)

            # Прокручиваем вниз до кнопки
            try:
                # Ищем кнопку "Смотреть еще"
                show_more_button = driver.find_elements(
                    By.CSS_SELECTOR,
                    "a.ShowMoreButton_showMoreLink__PJ15s, a.Pagination_showMore__7eqKr"
                )

                if not show_more_button:
                    print("[Znanie] Кнопка 'Смотреть еще' не найдена. Завершаем сбор.")
                    break

                button = show_more_button[0]

                # Прокручиваем до кнопки
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                time.sleep(0.5)

                # Пытаемся кликнуть
                try:
                    driver.execute_script("arguments[0].click();", button)
                except WebDriverException:
                    try:
                        button.click()
                    except Exception:
                        break

                # Ждём загрузки новых элементов
                time.sleep(wait_seconds)

            except (TimeoutException, Exception) as e:
                print(f"[Znanie] Ошибка при поиске/нажатии кнопки: {e}")
                break

        # Финальный сбор ссылок
        soup = BeautifulSoup(driver.page_source, "html.parser")
        event_items = soup.select("div.EventsList_listItem__UCayX")
        for item in event_items:
            link_elem = item.select_one("a[href*='/events/']")
            if link_elem:
                href = link_elem.get("href", "")
                normalized = normalize_link(href)
                if normalized and normalized not in seen_links:
                    seen_links.add(normalized)
                    links.append(normalized)

    finally:
        # Закрываем драйвер только если мы его создали
        if should_close_driver:
            driver.quit()

    return links


def extract_datetime(date_text: str, time_text: str) -> tuple[str, str]:
    """Извлекает дату и время из текстовых блоков Знания.

    Args:
        date_text: Текст с датой (например, "01 октября" или "01 октября 2025")
        time_text: Текст со временем (например, "в 15:00")

    Returns:
        tuple: (start_date, end_date) в формате "DD.MM.YYYY HH:MM"
    """
    months = {
        "января": "01",
        "февраля": "02",
        "марта": "03",
        "апреля": "04",
        "мая": "05",
        "июня": "06",
        "июля": "07",
        "августа": "08",
        "сентября": "09",
        "октября": "10",
        "ноября": "11",
        "декабря": "12",
    }

    if not date_text:
        return "", ""

    # Извлекаем день, месяц и (опционально) год из даты
    # Например: "01 октября" или "01 октября 2025"
    date_match = re.search(r"(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?", date_text, flags=re.IGNORECASE)
    if not date_match:
        return "", ""

    day = date_match.group(1)
    month_word = date_match.group(2).lower()
    month = months.get(month_word, "01")

    # Если год указан, используем его, иначе - текущий год
    year = date_match.group(3) if date_match.group(3) else str(time.localtime().tm_year)

    # Извлекаем время (например, "в 15:00" -> "15:00")
    time_str = ""
    if time_text:
        time_match = re.search(r"(\d{1,2}):(\d{2})", time_text)
        if time_match:
            hours = time_match.group(1).zfill(2)
            minutes = time_match.group(2)
            time_str = f"{hours}:{minutes}"

    if time_str:
        start_date = f"{day.zfill(2)}.{month}.{year} {time_str}"
        # Для Знания обычно только время начала, конца нет
        end_date = ""
        return start_date, end_date

    # Если время не найдено, возвращаем только дату
    start_date = f"{day.zfill(2)}.{month}.{year}"
    return start_date, ""


def parse_event_page(driver: webdriver.Chrome, url: str, timeout: int = 15) -> Dict[str, str]:
    """Парсит страницу мероприятия Знания с использованием Selenium.

    Args:
        driver: Экземпляр WebDriver
        url: URL страницы мероприятия
        timeout: Таймаут для загрузки страницы
    """
    try:
        driver.get(url)
        time.sleep(2)  # Даём время на загрузку динамического контента
        soup = BeautifulSoup(driver.page_source, "html.parser")
    except Exception as e:
        print(f"[parse_event_page] Ошибка загрузки {url}: {e}")
        return {
            "title": "",
            "link": url,
            "description": "",
            "start_date": "",
            "end_date": "",
            "image": "",
            "online": "false",
        }

    # --- Название ---
    title = ""
    title_tag = soup.select_one("h1.Cover_title__MJnV_ span")
    if title_tag:
        title = title_tag.get_text(strip=True)
    if not title:
        # Пробуем альтернативный селектор
        title_tag = soup.select_one("h1[itemprop='name'] span")
        if title_tag:
            title = title_tag.get_text(strip=True)
    if not title:
        title = "Без названия"

    # --- Описание ---
    description = ""
    description_node = soup.select_one("div.HtmlContent_block__7nXx5")
    if description_node:
        description = " ".join(description_node.stripped_strings)

    # --- Дата и время ---
    date_text = ""
    time_text = ""
    # Сначала находим родительский блок с датой
    date_container = soup.select_one("div.About_infoItemText__Za_fB")
    if date_container:
        # Внутри контейнера ищем блоки с датой
        date_nodes = date_container.select("div.About_infoItemDate__s0Ri1")
        if len(date_nodes) >= 1:
            # Ищем span внутри первого div
            span = date_nodes[0].select_one("span")
            if span:
                date_text = span.get_text(strip=True)
            else:
                # Если span не найден, пробуем get_text напрямую
                date_text = date_nodes[0].get_text(strip=True)
        if len(date_nodes) >= 2:
            # Ищем span внутри второго div
            span = date_nodes[1].select_one("span")
            if span:
                time_text = span.get_text(strip=True)
            else:
                # Если span не найден, пробуем get_text напрямую
                time_text = date_nodes[1].get_text(strip=True)

    start_date, end_date = extract_datetime(date_text, time_text)
    # Если end_date пустой, дублируем start_date (на сайте Знания нет даты окончания)
    if start_date and not end_date:
        end_date = start_date

    # Для Знания по умолчанию offline
    online = "false"

    # Изображение оставляем пустым
    image = ""

    return {
        "title": title,
        "link": url,
        "description": description,
        "start_date": start_date,
        "end_date": end_date,
        "image": image,
        "online": online,
    }


def load_existing_links(filename: str = COMMON_CSV_FILE) -> set:
    """Загружает существующие ссылки из CSV."""
    links = set()
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("link"):
                    links.add(row["link"])
    return links


def save_to_csv(rows: List[Dict[str, str]], filename: str = COMMON_CSV_FILE):
    """Сохраняет мероприятия в CSV, пропуская дубликаты."""
    fieldnames = ["title", "link", "description", "start_date", "end_date", "image", "online"]
    existing_links = load_existing_links(filename)
    new_rows = [r for r in rows if r.get("link") and r["link"] not in existing_links]

    if not new_rows:
        print("[CSV] Нет новых мероприятий для записи.")
        return

    file_exists = os.path.exists(filename)
    mode = "a" if file_exists else "w"

    with open(filename, mode, encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        if not file_exists:
            writer.writeheader()
        for row in new_rows:
            out = {k: (row.get(k) or "false" if k == "online" else row.get(k) or "") for k in fieldnames}
            writer.writerow(out)

    print(f"[CSV] Записано новых мероприятий: {len(new_rows)} → {filename}")


def main(headless: bool = True):
    """Главная функция парсинга Знания."""
    # Создаём драйвер один раз для всего процесса парсинга
    driver = setup_driver(headless=headless)
    results = []

    try:
        print("[Znanie] Сбор ссылок...")
        # Передаём драйвер в get_event_links для переиспользования
        links = get_event_links(START_URL, driver=driver, headless=headless)
        print(f"[Znanie] Найдено ссылок: {len(links)}")

        # Используем тот же драйвер для парсинга страниц мероприятий
        for i, link in enumerate(links, start=1):
            print(f"[Znanie] ({i}/{len(links)}) {link}")
            data = parse_event_page(driver, link)
            results.append(data)
            time.sleep(0.3)
    finally:
        driver.quit()

    save_to_csv(results, filename=COMMON_CSV_FILE)
    print(f"[Znanie] Результат сохранён в {COMMON_CSV_FILE}")


if __name__ == "__main__":
    main()

