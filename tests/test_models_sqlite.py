"""
Тестовые модели для SQLite (без Vector и NOW()).
"""
from sqlalchemy import Column, String, Integer, Float, Date, Boolean, TIMESTAMP, ForeignKey, text, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import uuid
from datetime import datetime

# Создаем отдельную базу для тестов
TestBase = declarative_base()


# Кастомный тип для UUID в SQLite
class GUID(TypeDecorator):
    """Platform-independent GUID type for SQLite."""
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(value)
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value


# Для SQLite используем String вместо Vector и datetime('now') вместо NOW()
class TestClusters(TestBase):
    __tablename__ = "clusters"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    centroid = Column(String)  # BLOB для SQLite
    created_at = Column(TIMESTAMP, default=lambda: datetime.now())
    
    directions = relationship("TestDirections", back_populates="cluster")

class TestDirections(TestBase):
    __tablename__ = "directions"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    cluster_id = Column(GUID(), ForeignKey("clusters.id", ondelete="SET NULL"))
    created_at = Column(TIMESTAMP, default=lambda: datetime.now())
    
    cluster = relationship("TestClusters", back_populates="directions")
    students = relationship("TestStudents", back_populates="direction")

class TestStudents(TestBase):
    __tablename__ = "students"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    participant_id = Column(String, unique=True, nullable=False)
    institution = Column(String)
    direction_id = Column(GUID(), ForeignKey("directions.id", ondelete="SET NULL"))
    profile_embedding = Column(String)  # BLOB для SQLite
    created_at = Column(TIMESTAMP, default=lambda: datetime.now())
    
    direction = relationship("TestDirections", back_populates="students")
    recommendations = relationship("TestRecommendations", back_populates="student")
    feedback = relationship("TestFeedback", back_populates="student")
    favorites = relationship("TestFavorites", back_populates="student")
    bot_user = relationship("TestBotUsers", back_populates="student", uselist=False)

class TestEvents(TestBase):
    __tablename__ = "events"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    short_description = Column(String)
    description = Column(String)
    format = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    link = Column(String)
    image_url = Column(String)
    vector_embedding = Column(String)  # BLOB для SQLite
    likes_count = Column(Integer, default=0)
    dislikes_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now())
    
    recommendations = relationship("TestRecommendations", back_populates="event")
    favorites = relationship("TestFavorites", back_populates="event")

class TestBotUsers(TestBase):
    __tablename__ = "bot_users"
    telegram_id = Column(Integer, primary_key=True)
    student_id = Column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), unique=True)
    username = Column(String)
    last_activity = Column(TIMESTAMP, default=lambda: datetime.now())
    email = Column(String)
    is_linked = Column(Boolean, default=False)
    
    student = relationship("TestStudents", back_populates="bot_user")

class TestFavorites(TestBase):
    __tablename__ = "favorites"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    event_id = Column(GUID(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now())
    
    student = relationship("TestStudents", back_populates="favorites")
    event = relationship("TestEvents", back_populates="favorites")

class TestRecommendations(TestBase):
    __tablename__ = "recommendations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(GUID(), ForeignKey("students.id", ondelete="CASCADE"))
    event_id = Column(GUID(), ForeignKey("events.id", ondelete="CASCADE"))
    score = Column(Float)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now())
    
    student = relationship("TestStudents", back_populates="recommendations")
    event = relationship("TestEvents", back_populates="recommendations")

class TestFeedback(TestBase):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(GUID(), ForeignKey("students.id", ondelete="CASCADE"))
    rating = Column(Integer)
    comment = Column(String)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now())
    
    student = relationship("TestStudents", back_populates="feedback")

