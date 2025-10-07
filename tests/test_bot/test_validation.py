import pytest
from src.bot.services.validation import is_valid_utmn_email

@pytest.mark.parametrize("email, expected", [
    ("stud0000123456@study.utmn.ru", True),      # ✅ Правильный
    ("stud0000987654@study.utmn.ru", True),      # ✅ Правильный
    ("stud0000123456@study.utmn.com", False),    # ❌ Неправильный домен
    ("stud000012345@study.utmn.ru", False),      # ❌ Слишком мало цифр (5 вместо 6)
    ("stud00001234567@study.utmn.ru", False),    # ❌ Слишком много цифр (7 вместо 6)
    ("stud0012345678@study.utmn.ru", False),     # ❌ Неправильный префикс (stud00 вместо stud0000)
    ("stud0000abcdef@study.utmn.ru", False),     # ❌ Буквы вместо цифр
    ("", False),                                 # ❌ Пустая строка
    ("stud0000123456@study.utmn.ruu", False),    # ❌ Лишняя буква в домене
    ("stud0000123456@study.utmn.r", False),      # ❌ Неправильный домен
])
def test_is_valid_utmn_email(email, expected):
    assert is_valid_utmn_email(email) == expected