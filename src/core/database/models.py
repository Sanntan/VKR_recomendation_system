from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Date,
    Boolean,
    TIMESTAMP,
    ForeignKey,
    text
)
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector


from sqlalchemy.orm import declarative_base, relationship
import uuid

Base = declarative_base()

# -------------------------------
# Таблица студентов
# -------------------------------
class Students(Base):
    __tablename__ = "students"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(String, unique=True, nullable=False)
    institution = Column(String)
    specialty = Column(String)
    profile_embedding = Column(Vector(768))
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))

    # обратные связи
    recommendations = relationship("Recommendations", back_populates="student")
    feedback = relationship("Feedback", back_populates="student")

# -------------------------------
# Telegram-пользователи
# -------------------------------
class BotUsers(Base):
    __tablename__ = "bot_users"

    telegram_id = Column(Integer, primary_key=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), unique=True)
    username = Column(String)
    last_activity = Column(TIMESTAMP, server_default=text("NOW()"))
    email = Column(String)
    is_linked = Column(Boolean, default=False)

# -------------------------------
# Направления
# -------------------------------
class Directions(Base):
    __tablename__ = "directions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)

# -------------------------------
# Категории
# -------------------------------
class Categories(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))

# -------------------------------
# Связь категорий и направлений
# -------------------------------
class CategoryDirections(Base):
    __tablename__ = "category_directions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"))
    direction_id = Column(UUID(as_uuid=True), ForeignKey("directions.id", ondelete="CASCADE"))

# -------------------------------
# Мероприятия
# -------------------------------
class Events(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    short_description = Column(String)
    description = Column(String)
    format = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    link = Column(String)
    image_url = Column(String)
    vector_embedding = Column(Vector(768))
    likes_count = Column(Integer, default=0)
    dislikes_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))

    categories = relationship("EventCategories", back_populates="event")

# -------------------------------
# Связь мероприятие ↔ категория
# -------------------------------
class EventCategories(Base):
    __tablename__ = "event_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"))
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"))

    event = relationship("Events", back_populates="categories")

# -------------------------------
# Рекомендации
# -------------------------------
class Recommendations(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"))
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"))
    score = Column(Float)
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))

    student = relationship("Students", back_populates="recommendations")

# -------------------------------
# Отзывы
# -------------------------------
class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"))
    rating = Column(Integer)
    comment = Column(String)
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))

    student = relationship("Students", back_populates="feedback")
