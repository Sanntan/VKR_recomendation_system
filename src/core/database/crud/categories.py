from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from src.core.database.models import Categories
from uuid import UUID

# -------------------------------
# CREATE
# -------------------------------
def create_category(db: Session, title: str):
    category = Categories(title=title)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category

# -------------------------------
# READ
# -------------------------------
def get_category_by_id(db: Session, category_id: UUID):
    return db.get(Categories, category_id)

def get_all_categories(db: Session, limit: int = 100):
    stmt = select(Categories).limit(limit)
    return db.execute(stmt).scalars().all()

# -------------------------------
# DELETE
# -------------------------------
def delete_category(db: Session, category_id: UUID):
    db.execute(delete(Categories).where(Categories.id == category_id))
    db.commit()
    return True

def delete_all_categories(db: Session):
    db.execute(delete(Categories))
    db.commit()
