import csv
import os
import re
import time
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "https://leader-id.ru"
START_URL = (
    "https://leader-id.ru/events?actual=1&cityId=1285249&registrationActual=1&sort=date"
)
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


def smooth_scroll(driver, step: int = 500, delay: float = 0.4):
    """Плавно прокручивает страницу вниз небольшими шагами."""
    last_height = driver.execute_script("return document.body.scrollHeight") or 0
    y = 0
    while y < last_height:
        y += step
        driver.execute_script(f"window.scrollTo(0, {y});")
        time.sleep(delay)
        new_height = driver.execute_script("return document.body.scrollHeight") or 0
        if new_height > last_height:
            last_height = new_height


def get_event_links(
        start_url: str,
        scroll_limit: int = 10,
        wait_seconds: float = 2.0,
        headless: bool = False,
) -> List[Dict[str, str]]:
    """Прокручивает страницу Leader-ID и собирает ссылки на мероприятия,
       исключая те, где в названии есть '#АП ТюмГУ'.
       Возвращает список словарей с ключами 'link' и 'online'."""
    driver = setup_driver(headless=headless)
    driver.get(start_url)
    time.sleep(4)  # дождаться загрузки

    last_height = driver.execute_script("return document.body.scrollHeight")
    seen_links = set()
    result_links = []

    for i in range(scroll_limit):
        print(f"[Scroll] {i + 1}/{scroll_limit}...")
        smooth_scroll(driver, step=400, delay=0.5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        cards = soup.select("div.app-card-event.x4EOhs8Tyx7D")

        for card in cards:
            link = card.get("share-link")
            if not link or link in seen_links:
                continue

            title_node = card.select_one("h4.app-card-event__title a.app-card-event__link")
            title = title_node.get_text(strip=True) if title_node else ""
            if "#АП ТюмГУ" in title:
                continue

            # Проверяем наличие тега "Онлайн" в карточке мероприятия
            online = False
            # Ищем кнопки с классом app-card-event__category внутри карточки
            category_buttons = card.select("button.app-card-event__category")
            for button in category_buttons:
                button_text = button.get_text(strip=True)
                if button_text == "Онлайн":
                    online = True
                    break

            seen_links.add(link)
            result_links.append({
                "link": link,
                "online": str(online).lower()
            })

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    driver.quit()
    return result_links


def _normalize_src(src: str) -> str:
    """Нормализует ссылку на изображение до абсолютной."""
    if not src:
        return ""
    s = src.strip()
    if s.startswith("//"):
        return "https:" + s
    if s.startswith("/"):
        return BASE_URL.rstrip("/") + s
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return BASE_URL.rstrip("/") + "/" + s


def parse_event_page(url: str, timeout: int = 15, online: str = "false") -> Dict[str, str]:
    """Парсит страницу конкретного мероприятия Leader-ID.

    Args:
        url: URL страницы мероприятия
        timeout: Таймаут для запроса
        online: Информация об онлайн/оффлайн ("true" или "false")
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        print(f"[requests] Ошибка запроса {url}: {e}")
        return {
            "title": "",
            "link": url,
            "description": "",
            "start_date": "",
            "end_date": "",
            "image": "",
            "online": "false",
        }

    if resp.status_code != 200:
        print(f"[requests] Предупреждение: код {resp.status_code} для {url}")

    # Учитываем кодировку
    if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")

    # --- Название ---
    title_tag = soup.select_one('h2.app-heading-2[data-qa="eventTitle"]')
    title = title_tag.get_text(strip=True) if title_tag else "Без названия"

    # --- Изображение ---
    img_tag = soup.select_one("img.N7q+gJIOp1nZ, img.event-about__poster, .QdSHhdPbThT1 img")
    image = _normalize_src(img_tag.get("src", "").strip()) if img_tag else ""

    # --- Дата и время ---
    # Ищем среди <p> именно строку, где есть время (часы:минуты)
    date_text = ""
    for p in soup.select(".VgeeIlXEs99- p.app-paragraph.app-paragraph--sm"):
        txt = " ".join(p.stripped_strings)
        if re.search(r"\d{1,2}:\d{2}", txt):
            date_text = txt
            break

    # Срезаем хвост про часовой пояс/город
    if date_text:
        # убираем всё от "по ..." (по Екатеринбургскому времени ...) и дальше
        date_text = re.sub(r"\s*по .*", "", date_text, flags=re.IGNORECASE).strip()) #dsada
        # на всякий случай убираем завершающиеся скобки, если остались
        date_text = re.sub(r"\s*\(.*?\)\s*$", "", date_text).strip()

    start_date, end_date = extract_datetime(date_text)

    # --- Описание ---
    description = ""
    about_node = soup.select_one("div.app-editor-view[data-qa='draftEventDescription']")
    if about_node:
        # Удаляем сетевой блок, если он встретится (иногда он вне about_node — он не помешает)
        networking = soup.select_one("div.event-about__networking")
        if networking:
            networking.decompose()
        description = " ".join(about_node.stripped_strings)

    # Информация об онлайн/оффлайн уже определена при сборе ссылок
    # Используем переданный параметр

    return {
        "title": title,
        "link": url,
        "description": description,
        "start_date": start_date,
        "end_date": end_date,
        "image": image,
        "online": online,  # Используем переданное значение
    }


def extract_datetime(date_text: str) -> (str, str):
    """Извлекает даты/время из строк Leader-ID в несколько форматов."""
    if not date_text:
        return "", ""

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

    # 1) "28 октября, с 08:00 до 22:00"
    m1 = re.search(r"(\d{1,2}) (\w+),\s*с (\d{2}:\d{2}) до (\d{2}:\d{2})", date_text, flags=re.IGNORECASE)
    if m1:
        day, month_word, start_time, end_time = m1.groups()
        month = months.get(month_word.lower(), "01")
        year = time.localtime().tm_year
        return f"{day.zfill(2)}.{month}.{year} {start_time}", f"{day.zfill(2)}.{month}.{year} {end_time}"

    # 2) "10 января 2026, с 18:00 до 20:30"
    m2 = re.search(
        r"(\d{1,2}) (\w+) (\d{4}),\s*с (\d{2}:\d{2}) до (\d{2}:\d{2})",
        date_text,
        flags=re.IGNORECASE,
    )
    if m2:
        day, month_word, year, start_time, end_time = m2.groups()
        month = months.get(month_word.lower(), "01")
        return f"{day.zfill(2)}.{month}.{year} {start_time}", f"{day.zfill(2)}.{month}.{year} {end_time}"

    # 3) "23 октября 2025, 10:00 — 15 декабря 2025, 20:00" (длинный диапазон, оба с годом)
    m3 = re.search(
        r"(\d{1,2}) (\w+) (\d{4}), (\d{2}:\d{2})\s*[—–-]\s*(\d{1,2}) (\w+) (\d{4}), (\d{2}:\d{2})",
        date_text,
        flags=re.IGNORECASE,
    )
    if m3:
        d1, m1w, y1, t1, d2, m2w, y2, t2 = m3.groups()
        return (
            f"{d1.zfill(2)}.{months.get(m1w.lower(), '01')}.{y1} {t1}",
            f"{d2.zfill(2)}.{months.get(m2w.lower(), '01')}.{y2} {t2}",
        )

    # 4) "23 октября 2025, 10:00 — 15 декабря, 20:00" (вторая часть без года)
    m4 = re.search(
        r"(\d{1,2}) (\w+) (\d{4}), (\d{2}:\d{2})\s*[—–-]\s*(\d{1,2}) (\w+), (\d{2}:\d{2})",
        date_text,
        flags=re.IGNORECASE,
    )
    if m4:
        d1, m1w, y1, t1, d2, m2w, t2 = m4.groups()
        return (
            f"{d1.zfill(2)}.{months.get(m1w.lower(), '01')}.{y1} {t1}",
            f"{d2.zfill(2)}.{months.get(m2w.lower(), '01')}.{y1} {t2}",
        )

    # 5) "12 января 2026, 18:30" (одна точка)
    m53 = re.search(r"(\d{1,2}) (\w+) (\d{4}), (\d{2}:\d{2})", date_text, flags=re.IGNORECASE) #dsada
    if m5:
        d, mw, y, t = m5.groups()
        return f"{d.zfill(2)}.{months.get(mw.lower(), '01')}.{y} {t}", ""

    print(f"[!] Не удалось распознать дату: {date_text}")
    return "", ""


def load_existing_links(filename: str = COMMON_CSV_FILE) -> set:
    links = set()
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("link"):
                    links.add(row["link"])
    return links


def save_to_csv(rows: List[Dict[str, str]], filename: str = COMMON_CSV_FILE):
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


def main(headless: bool = False):
    print("[LeaderID] Сбор ссылок..."); # dsada
    event_data = get_event_links(START_URL, scroll_limit=10, wait_seconds=2.5, headless=headless)
    print(f"[LeaderID] Найдено ссылок: {len(event_data)}")

    results = []
    for i, event_info in enumerate(event_data, 1):
        link = event_info["link"]
        online = event_info["online"]
        print(f"[LeaderID] ({i}/{len(event_data)}) {link}")
        data = parse_event_page(link, online=online)
        results.append(data)
        time.sleep(0.4)

    save_to_csv(results)


if __name__ == "__main__":
    main()
