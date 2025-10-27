import time

from parse_utmn import (
    START_URL,
    get_event_links,
    parse_event_page,
    save_to_csv,
)


def main():
    click_limit = 2
    headless = True
    print("[Main] Сбор ссылок через Selenium...")
    links = get_event_links(START_URL, max_clicks=click_limit, headless=headless)
    print(f"[Main] Найдено ссылок: {len(links)}")
    seen = set()
    unique_links = []
    for l in links:
        if l not in seen:
            unique_links.append(l)
            seen.add(l)
    results = []
    for i, link in enumerate(unique_links, start=1):
        print(f"[Main] ({i}/{len(unique_links)}) Парсим страницу: {link}")
        data = parse_event_page(link)
        results.append(data)
        time.sleep(0.25)
    save_to_csv(results, filename="events.csv")
    print("[Main] Результат сохранён в events.csv")


if __name__ == "__main__":
    main()
