import re

def is_valid_participant_id(participant_id: str) -> bool:
    """
    Проверяет корректность participant_id.
    Пока что просто проверяем, что это непустая строка.
    В будущем можно добавить более строгую валидацию.
    """
    return bool(participant_id and participant_id.strip())