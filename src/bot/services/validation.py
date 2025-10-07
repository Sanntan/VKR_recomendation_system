import re

def is_valid_utmn_email(email: str) -> bool:
    """
    Проверяет, соответствует ли email корпоративному формату ТюмГУ.
    Формат: stud0000######@study.utmn.ru, где # - цифры от 0 до 9.
    """
    pattern = r'^stud0000\d{6}@study\.utmn\.ru$'
    return re.match(pattern, email) is not None