from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from src.core.database.connection import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def db_dependency(db: Session = Depends(get_db)) -> Session:
    return db

