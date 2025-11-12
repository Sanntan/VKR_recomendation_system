"""Модуль для генерации текстового профиля студента на основе компетенций и векторизации."""

from typing import Dict, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

# Инициализация модели (та же, что для мероприятий)
EMBEDDER = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# Список всех компетенций (28 компетенций)
COMPETENCIES = [
    "Анализ информации",
    "Планирование",
    "Ориентация на результат",
    "Стрессоустойчивость",
    "Партнерство/Сотрудничество",
    "Следование правилам и процедурам",
    "Саморазвитие",
    "Лидерство",
    "Эмоциональный интеллект",
    "Клиентоориентированность",
    "Коммуникация",
    "Пассивный словарный запас",
    "Автономия",
    "Альтруизм",
    "Вызов",
    "Заработок",
    "Карьера",
    "Креативность",
    "Отношения",
    "Признание",
    "Принадлежность",
    "Саморазвитие.1",
    "Смысл",
    "Сотрудничество",
    "Стабильность",
    "Традиция",
    "Управление",
    "Условия труда",
]


def categorize_competency(t_score: int) -> str:
    """
    Категоризирует компетенцию по т-баллу.

    Args:
        t_score: Т-балл компетенции (200-800)

    Returns:
        "motivator" (600-800): ресурсная зона, конкурентное преимущество
        "neutral" (400-599): потенциал для развития, но не требует дополнительных шагов
        "demotivator" (200-399): ниже необходимого уровня, требуется развитие
        "unknown": некорректное значение
    """
    if 600 <= t_score <= 800:
        return "motivator"
    elif 400 <= t_score < 600:
        return "neutral"
    elif 200 <= t_score < 400:
        return "demotivator"
    else:
        return "unknown"


def generate_profile_description(
    specialty: Optional[str],
    competencies: Dict[str, int]
) -> str:
    """
    Генерирует текстовое описание профиля студента на основе специальности и компетенций.

    Args:
        specialty: Название специальности (направления подготовки)
        competencies: Словарь {название_компетенции: т-балл}

    Returns:
        Текстовое описание профиля для векторизации
    """
    parts = []

    # 1. Специальность
    if specialty:
        parts.append(f"Специальность: {specialty}.")

    # 2. Мотиваторы (сильные стороны, 600-800)
    motivators = [
        name for name, score in competencies.items()
        if categorize_competency(score) == "motivator"
    ]
    if motivators:
        motivators_text = ", ".join(motivators)
        parts.append(
            f"Сильные стороны и конкурентные преимущества: {motivators_text}. "
            f"Эти компетенции развиты выше среднего уровня и являются ресурсной зоной."
        )

    # 3. Демотиваторы (зоны развития, 200-399)
    demotivators = [
        name for name, score in competencies.items()
        if categorize_competency(score) == "demotivator"
    ]
    if demotivators:
        demotivators_text = ", ".join(demotivators)
        parts.append(
            f"Зоны развития: {demotivators_text}. "
            f"Эти компетенции требуют дополнительного развития и проявляются ниже необходимого уровня."
        )

    # 4. Средние компетенции (400-599)
    neutrals = [
        name for name, score in competencies.items()
        if categorize_competency(score) == "neutral"
    ]
    if neutrals:
        # Ограничиваем количеством для читаемости
        neutrals_text = ", ".join(neutrals[:8])
        if len(neutrals) > 8:
            neutrals_text += f" и еще {len(neutrals) - 8} компетенций"
        parts.append(
            f"Компетенции со средним уровнем развития: {neutrals_text}. "
            f"Эти компетенции имеют потенциал для развития."
        )

    # Формируем итоговое описание
    description = " ".join(parts)

    # Добавляем общий контекст
    if not description:
        description = "Студент с базовым профилем компетенций."
    else:
        description += (
            " Студент заинтересован в мероприятиях, которые помогают развивать компетенции "
            "и использовать сильные стороны для профессионального роста."
        )

    return description


def vectorize_student_profile(
    specialty: Optional[str],
    competencies: Dict[str, int]
) -> Optional[np.ndarray]:
    """
    Векторизует профиль студента на основе специальности и компетенций.

    Args:
        specialty: Название специальности
        competencies: Словарь {название_компетенции: т-балл}

    Returns:
        Вектор размерности 384 (или None при ошибке)
    """
    try:
        # Генерируем текстовое описание
        profile_text = generate_profile_description(specialty, competencies)

        # Векторизуем описание (нормализуем для cosine similarity)
        embedding = EMBEDDER.encode([profile_text], normalize_embeddings=True)[0]

        return embedding
    except Exception as e:
        print(f"❌ Ошибка векторизации профиля студента: {e}")
        return None


def update_profile_embedding_from_competencies(
    specialty: Optional[str],
    competencies: Optional[Dict[str, int]]
) -> Optional[np.ndarray]:
    """
    Обновляет профильный вектор на основе компетенций.
    Если компетенции не предоставлены, возвращает None.

    Args:
        specialty: Название специальности
        competencies: Словарь компетенций {название: т-балл}

    Returns:
        Вектор размерности 384 или None
    """
    if not competencies:
        return None

    return vectorize_student_profile(specialty, competencies)


def vectorize_profiles_batch(
    profile_texts: list[str],
    batch_size: int = 32,
    show_progress_bar: bool = True
) -> np.ndarray:
    """
    Векторизует несколько профилей одновременно (батчевая обработка).
    Значительно быстрее, чем векторизация по одному.

    Args:
        profile_texts: Список текстовых описаний профилей
        batch_size: Размер батча для обработки
        show_progress_bar: Показывать ли прогресс-бар

    Returns:
        Массив векторов размерности [len(profile_texts), 384]
    """
    if not profile_texts:
        return np.array([])
    
    try:
        # Батчевая векторизация (значительно быстрее)
        embeddings = EMBEDDER.encode(
            profile_texts,
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar
        )
        return embeddings
    except Exception as e:
        print(f"❌ Ошибка батчевой векторизации профилей: {e}")
        raise

