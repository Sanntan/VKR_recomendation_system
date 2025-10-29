import csv, requests, pytest
from src.parsing.parse_utmn import _normalize_src, BASE_URL, parse_event_page, save_to_csv, get_event_links, setup_driver


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
    <article class="article article-detail article-detail__block">
        <h1>Тестовое событие</h1>
        <div class="article-detail__preview">
            <img src="/upload/img/test.webp">
        </div>
        <p>Описание события.</p>
    </article>
    """

    def fake_get(url, **kwargs):
        class R:
            status_code = 200
            text = html
            encoding = "utf-8"
        return R()

    monkeypatch.setattr("src.parsing.parse_utmn.requests.get", fake_get)

    data = parse_event_page("https://fake-url")
    assert data["title"] == "Тестовое событие"
    assert "Описание" in data["description"]
    assert data["image"].endswith("test.webp")
    assert data["start_date"] == ""
    assert data["end_date"] == ""


# ---------- 3. Тест сохранения CSV (не дублирует записи) ----------
def test_save_to_csv_adds_only_new(tmp_path):

    file = tmp_path / "events.csv"
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


# ---------- 4. Тест корректной очистки текста ----------
def test_parse_event_page_text_normalization(monkeypatch):

    html = """
    <article class="article article-detail article-detail__block">
        <h1>Тест</h1>
        <p>Строка 1</p>
        <p>   </p>
        <p>Строка 2</p>
    </article>
    """

    def fake_get(url, **kwargs):
        class R:
            status_code = 200
            text = html
            encoding = "utf-8"
        return R()

    monkeypatch.setattr("src.parsing.parse_utmn.requests.get", fake_get)

    data = parse_event_page("x")
    assert "\n\n" not in data["description"]
    assert "Строка 1" in data["description"]
    assert "Строка 2" in data["description"]


# ---------- 5. Тест получения ссылок (уникальность и нормализация) ----------
def test_get_event_links_unique_and_normalized(monkeypatch):

    class FakeElement:
        def __init__(self, href):
            self.href = href
        def get_attribute(self, attr):
            return self.href

    class FakeDriver:
        def __init__(self):
            self.clicks = 0
        def get(self, url): pass
        def find_elements(self, *_, **__):
            base = self.clicks * 3
            return [
                FakeElement(f"/news/events/test-{base + 1}/"),
                FakeElement(f"https://utmn.ru/news/events/test-{base + 2}/"),
                FakeElement(f"/news/events/test-{base + 3}/"),
            ]
        def find_element(self, *_, **__):
            self.clicks += 1
            if self.clicks > 2:
                raise Exception("No more button")
            return object()
        def execute_script(self, *_): pass
        def quit(self): pass

    monkeypatch.setattr("src.parsing.parse_utmn.setup_driver", lambda **_: FakeDriver())

    links = get_event_links(BASE_URL + "/news/events/", max_clicks=3, headless=True)

    assert len(links) == len(set(links))
    assert all(link.startswith(BASE_URL) for link in links)
    assert any("test-1" in link for link in links)


# ---------- 6. Тест устойчивости к ошибкам сети ----------
def test_parse_event_page_handles_request_error(monkeypatch):

    def fake_get(*_, **__):
        raise requests.RequestException("network failure")

    monkeypatch.setattr("src.parsing.parse_utmn.requests.get", fake_get)

    result = parse_event_page("https://fake-url")
    assert isinstance(result, dict)
    assert set(result.keys()) == {"title", "link", "description", "start_date", "end_date", "image"}
    assert result["title"] == ""
    assert result["description"] == ""
    assert result["image"] == ""
    assert result["start_date"] == ""
    assert result["end_date"] == ""
