#!/usr/bin/env python3
"""
Скрипт для добавления тестовых студентов в базу данных с синтетическими данными.

Создает 1-2 студента с:
- Уникальными participant_id
- Институтами
- Векторизованными профилями на основе описаний увлечений
- Связью с направлением "Математическое обеспечение и администрирование информационных систем"
"""

import sys
from pathlib import Path
from uuid import UUID

# Добавляем корень проекта в путь для импортов
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from src.core.database.connection import engine
from src.core.database.crud.directions import get_direction_by_title
from src.core.database.crud.students import create_student, get_student_by_participant_id
from src.core.database.models import Directions
from sqlalchemy import select


def create_synthetic_students():
    """Создать тестовых студентов с синтетическими данными."""
    
    # Инициализируем модель векторизации (та же, что используется в проекте)
    print("🤖 Инициализация модели векторизации...")
    embedder = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    print("✅ Модель загружена")
    
    # Синтетические данные студентов
    synthetic_students = [
        {
            "participant_id": "test_student_001",
            "institution": "Тюменский государственный университет",
            "interests_description": """
            Глубоко интересуюсь правовыми аспектами цифровых технологий, в частности, регулированием искусственного интеллекта и больших данных. 
            Изучаю вопросы кибербезопасности, цифрового права и этики в контексте развития технологий. 
            Участвую в научных дискуссиях о том, как право адаптируется к вызовам цифровой трансформации общества. 
            Особый интерес представляют проблемы авторского права в интернете и юридическая ответственность за действия AI.
            """
        },
        {
            "participant_id": "test_student_002",
            "institution": "Московский государственный университет",
            "interests_description": """
            Увлекаюсь литературоведением и исторической прозой. 
            Люблю анализировать художественные тексты, исследую взаимосвязь литературы и истории. 
            Интересуюсь вопросами сохранения культурного наследия через литературные произведения и исторические хроники. 
            В свободное время изучаю историю народов России и их отражение в современной литературе.
            """
        }
    ]
    
    target_direction_title = "Языкознание и литературоведение"
    
    with Session(engine) as db:
        print(f"\n🔍 Поиск направления: '{target_direction_title}'")
        
        # Найти направление по названию
        direction = get_direction_by_title(db, target_direction_title)
        
        if not direction:
            print(f"❌ Направление '{target_direction_title}' не найдено в базе данных!")
            print("📋 Доступные направления:")
            
            # Показать все доступные направления
            all_directions = db.execute(select(Directions)).scalars().all()
            for d in all_directions[:10]:  # Показать первые 10
                print(f"   - {d.title}")
            if len(all_directions) > 10:
                print(f"   ... и еще {len(all_directions) - 10} направлений")
            
            return
        
        print(f"✅ Найдено направление: '{direction.title}' (ID: {direction.id})")
        
        # Создать студентов
        created_count = 0
        
        for student_data in synthetic_students:
            try:
                print(f"\n👤 Создание студента: {student_data['participant_id']}")
                
                # Векторизовать описание увлечений
                print("🧮 Векторизация профиля...")
                embedding = embedder.encode([student_data['interests_description'].strip()], normalize_embeddings=True)[0]
                embedding_list = embedding.tolist()
                
                print(f"   📏 Размерность вектора: {len(embedding_list)}")
                
                # Создать студента
                student = create_student(
                    db=db,
                    participant_id=student_data['participant_id'],
                    institution=student_data['institution'],
                    direction_id=direction.id,
                    profile_embedding=embedding_list
                )
                
                print(f"✅ Студент создан с ID: {student.id}")
                created_count += 1
                
            except Exception as e:
                print(f"❌ Ошибка при создании студента {student_data['participant_id']}: {e}")
                db.rollback()
        
        print(f"\n🎉 Создано {created_count} тестовых студентов!")
        
        # Показать результаты
        if created_count > 0:
            print("\n📊 Проверка созданных студентов:")
            for student_data in synthetic_students:
                # Проверить, что студент создан
                student = get_student_by_participant_id(db, student_data['participant_id'])
                if student:
                    print(f"   ✅ {student.participant_id}: {student.institution}")
                    print(f"      Направление: {direction.title}")
                    print(f"      Вектор профиля: {len(student.profile_embedding)} измерений")
                else:
                    print(f"   ❌ {student_data['participant_id']}: не найден")


if __name__ == "__main__":
    print("🚀 Запуск скрипта добавления тестовых студентов")
    print("=" * 50)
    
    try:
        create_synthetic_students()
        print("\n✅ Скрипт выполнен успешно!")
    except Exception as e:
        print(f"\n❌ Ошибка выполнения скрипта: {e}")
        sys.exit(1)
