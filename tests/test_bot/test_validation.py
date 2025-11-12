import pytest
from src.bot.services.validation import is_valid_participant_id

@pytest.mark.parametrize("participant_id, expected", [
    ("test_001", True),           # ✅ Правильный
    ("participant_123", True),    # ✅ Правильный
    ("", False),                  # ❌ Пустая строка
    ("   ", False),               # ❌ Только пробелы
    ("valid_id", True),           # ✅ Валидный
])
def test_is_valid_participant_id(participant_id, expected):
    assert is_valid_participant_id(participant_id) == expected