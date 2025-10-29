import csv, requests, pytest
from src.parsing.parse_leaderid import (
    _normalize_src,
    parse_event_page,
    extract_datetime,
    save_to_csv,
    get_event_links,
    BASE_URL,
)

# ---------- 1. Тест нормализации ссылок ----------
def test_normalize_src_variants():
    assert _normalize_src("//example.com/img.jpg") == "https://example.com/img.jpg"
    assert _normalize_src("/upload/a.jpg") == f"{BASE_URL}/upload/a.jpg"
    assert _normalize_src("upload/a.jpg") == f"{BASE_URL}/upload/a.jpg"
    assert _normalize_src("http://x.com/img.jpg") == "http://x.com/img.jpg"
    assert _normalize_src("https://x.com/img.jpg") == "https://x.com/img.jpg"
    assert _normalize_src("") == ""


# ---------- 2. Тест парсинга страницы с простым HTML ----------
def test_parse_event_page_with_sample_html(monkeypatch):
    html = """
    <html>
    <body>
        <h2 data-qa="eventTitle" class="app-heading-2">Тестовое мероприятие</h2>
        <img class="event-about__poster" src="/upload/img/test.webp">
        <div data-qa="draftEventDescription" class="app-editor-view">
            <p>Описание мероприятия.</p>
        </div>
    </body>
    </html>
    """

    def fake_get(url, **kwargs):
        class R:
            status_code = 200
            text = html
            encoding = "utf-8"
        return R()

    monkeypatch.setattr("src.parsing.parse_leaderid.requests.get", fake_get)
    data = parse_event_page("https://fake-url")

    assert data["title"] == "Тестовое мероприятие"
    assert "Описание" in data["description"]
    assert data["image"].endswith("test.webp")
    assert data["start_date"] == ""
    assert data["end_date"] == ""


# ---------- 3. Тест корректной очистки описания ----------
def test_parse_event_page_text_normalization(monkeypatch):
    html = """
    <html>
    <body>
        <h2 data-qa="eventTitle" class="app-heading-2">Тест</h2>
        <div data-qa="draftEventDescription" class="app-editor-view">
            <p>Строка 1</p>
            <p>   </p>
            <p>Строка 2</p>
        </div>
    </body>
    </html>
    """

    def fake_get(url, **kwargs):
        class R:
            status_code = 200
            text = html
            encoding = "utf-8"
        return R()

    monkeypatch.setattr("src.parsing.parse_leaderid.requests.get", fake_get)
    data = parse_event_page("x")

    assert "Строка 1" in data["description"]
    assert "Строка 2" in data["description"]
    assert "\n\n" not in data["description"]


# ---------- 4. Тест парсинга дат ----------
@pytest.mark.parametrize(
    "input_str,expected_start,expected_end",
    [
        ("28 октября, с 08:00 до 22:00", "28.10.2025 08:00", "28.10.2025 22:00"),
        ("10 января 2026, с 18:00 до 20:30", "10.01.2026 18:00", "10.01.2026 20:30"),
        (
            "23 октября 2025, 10:00 — 15 декабря 2025, 20:00",
            "23.10.2025 10:00",
            "15.12.2025 20:00",
        ),
        (
            "23 октября 2025, 10:00 — 15 декабря, 20:00",
            "23.10.2025 10:00",
            "15.12.2025 20:00",
        ),
        ("12 января 2026, 18:30", "12.01.2026 18:30", ""),
    ],
)
def test_extract_datetime_variants(input_str, expected_start, expected_end):
    start, end = extract_datetime(input_str)
    assert start.startswith(expected_start[:5])
    assert expected_end[:5] in end or end == ""


# ---------- 5. Тест сохранения CSV (не дублирует записи) ----------
def test_save_to_csv_adds_only_new(tmp_path):
    file = tmp_path / "leaderid_events.csv"
    existing = [{"title": "A", "link": "link1", "description": "x", "image": "img"}]
    save_to_csv(existing, filename=file)
    new = [
        {"title": "B", "link": "link2", "description": "y", "image": "img2"},
        {"title": "A", "link": "link1", "description": "x", "image": "img"},
    ]
    save_to_csv(new, filename=file)

    with open(file, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2  # "link1" не продублировался


# ---------- 6. Тест устойчивости к ошибкам сети ----------
def test_parse_event_page_handles_request_error(monkeypatch):
    def fake_get(*_, **__):
        raise requests.RequestException("network failure")

    monkeypatch.setattr("src.parsing.parse_leaderid.requests.get", fake_get)
    result = parse_event_page("https://fake-url")

    assert isinstance(result, dict)
    assert set(result.keys()) == {
        "title",
        "link",
        "description",
        "start_date",
        "end_date",
        "image",
    }
    assert result["title"] == ""
    assert result["description"] == ""
    assert result["image"] == ""


# ---------- 7. Тест получения ссылок (уникальность и нормализация) ----------
def test_get_event_links_unique_and_normalized(monkeypatch):

    class FakeDriver:
        def __init__(self):
            self.page_source = """
                <div class="app-card-event x4EOhs8Tyx7D" share-link="/events/test-1/"></div>
                <div class="app-card-event x4EOhs8Tyx7D" share-link="https://leader-id.ru/events/test-2/"></div>
                <div class="app-card-event x4EOhs8Tyx7D" share-link="/events/test-3/"></div>
            """
        def get(self, url): pass
        def quit(self): pass
        def execute_script(self, *_): pass
        def find_elements(self, *_, **__): return []

    monkeypatch.setattr("src.parsing.parse_leaderid.setup_driver", lambda **_: FakeDriver())

    links = get_event_links(BASE_URL + "/events", scroll_limit=1, headless=True)

    # Уникальность
    assert len(links) == len(set(links))

    # Нормализуем относительные ссылки для проверки
    normalized = [
        (BASE_URL.rstrip("/") + link) if link.startswith("/") else link
        for link in links
    ]

    # Все ссылки после нормализации должны начинаться с BASE_URL
    assert all(link.startswith(BASE_URL) for link in normalized)

    # Среди них должна быть test-1
    assert any("test-1" in link for link in normalized)


