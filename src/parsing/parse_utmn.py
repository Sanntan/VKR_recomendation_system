import time
import csv
from typing import List, Dict
import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
import os

BASE_URL = "https://www.utmn.ru"
START_URL = f"{BASE_URL}/news/events/"


def setup_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


def get_event_links(start_url: str, max_clicks: int = 5, headless: bool = True, wait_seconds: float = 2.5) -> List[str]:
    driver = setup_driver(headless=headless)
    links: List[str] = []
    try:
        driver.get(start_url)
        wait = WebDriverWait(driver, 10)

        def count_articles():
            return len(driver.find_elements(By.CSS_SELECTOR, "article.article"))

        prev_count = count_articles()
        clicks = 0

        while clicks < max_clicks:
            anchors = driver.find_elements(By.CSS_SELECTOR, "article.article .article_title a")
            for a in anchors:
                href = a.get_attribute("href")
                if not href:
                    continue
                if href.startswith("/"):
                    href = BASE_URL.rstrip("/") + href
                if "/news/events/" in href and href.rstrip("/") != START_URL.rstrip("/"):
                    if href not in links:
                        links.append(href)
            try:
                btn = driver.find_element(By.ID, "btn_get-events")
            except Exception:
                break
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(0.4)
                driver.execute_script("arguments[0].click();", btn)
            except WebDriverException:
                try:
                    btn.click()
                except Exception:
                    break
            clicks += 1
            waited = 0.0
            timeout = 10.0
            tick = 0.5
            while waited < timeout:
                time.sleep(tick)
                waited += tick
                cur_count = count_articles()
                if cur_count > prev_count:
                    prev_count = cur_count
                    break
            time.sleep(wait_seconds)

        anchors = driver.find_elements(By.CSS_SELECTOR, "article.article .article_title a")
        for a in anchors:
            href = a.get_attribute("href")
            if not href:
                continue
            if href.startswith("/"):
                href = BASE_URL.rstrip("/") + href
            if "/news/events/" in href and href.rstrip("/") != START_URL.rstrip("/"):
                if href not in links:
                    links.append(href)
    finally:
        driver.quit()
    return links


def _normalize_src(src: str) -> str:
    if not src:
        return ""
    s = src.strip()
    if s.startswith("//"):
        return "https:" + s
    if s.startswith("/"):
        return BASE_URL.rstrip("/") + s
    if s.startswith("upload/"):
        return BASE_URL.rstrip("/") + "/" + s
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return BASE_URL.rstrip("/") + "/" + s


def parse_event_page(url: str, timeout: int = 12) -> Dict[str, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        print(f"[requests] Ошибка запроса {url}: {e}")
        return {"title": "", "link": url, "body": "", "image": ""}

    if resp.status_code != 200:
        print(f"[requests] Предупреждение: код {resp.status_code} для {url}")

    if resp.encoding is None or resp.encoding.lower() == 'iso-8859-1':
        resp.encoding = resp.apparent_encoding or 'utf-8'

    soup = BeautifulSoup(resp.text, "html.parser")

    article_node = soup.select_one("article.article-detail.article-detail__block")
    root = article_node if article_node is not None else soup

    title = ""
    first_h1 = root.find("h1")
    if first_h1:
        title = " ".join(first_h1.stripped_strings)
        first_h1.decompose()
    if not title:
        any_h1 = soup.find("h1")
        if any_h1:
            title = " ".join(any_h1.stripped_strings)
    if not title:
        title = "Без названия"

    image_url = ""
    for img in root.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original") or ""
        full = _normalize_src(src)
        if full:
            image_url = full
            break

    body_text = " ".join(root.stripped_strings)
    lines = [ln.rstrip() for ln in body_text.splitlines()]
    normalized_lines = []
    prev_empty = False
    for ln in lines:
        is_empty = (ln.strip() == "")
        if is_empty and prev_empty:
            continue
        normalized_lines.append(ln)
        prev_empty = is_empty
    body_text = "\n".join(normalized_lines).strip()

    return {"title": title, "link": url, "body": body_text, "image": image_url}


def load_existing_links(filename: str = "events.csv") -> set:
    links = set()
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                links.add(row.get("link"))
    return links


def save_to_csv(rows: List[Dict[str, str]], filename: str = "events.csv") -> None:
    fieldnames = ["title", "link", "body", "image"]
    existing_links = load_existing_links(filename)
    new_rows = [row for row in rows if row.get("link") not in existing_links]
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
            out = {k: (row.get(k) or "") for k in fieldnames}
            writer.writerow(out)
    print(f"[CSV] Записано новых мероприятий: {len(new_rows)}")
