# src/core/database/add_test_student.py
from sqlalchemy.orm import Session
from src.core.database.connection import engine
from src.core.database.models import Students

def add_test_student():
    with Session(engine) as session:
        student = Students(
            participant_id="TEST-001",
            institution="ТюмГУ",
            specialty="Прикладная информатика"
        )
        session.add(student)
        session.commit()
        print(f"✅ Студент добавлен: ID={student.id}, participant_id={student.participant_id}")

if __name__ == "__main__":
    try:
        add_test_student()
    except Exception as e:
        print(f"❌ Ошибка при добавлении студента: {e}")
