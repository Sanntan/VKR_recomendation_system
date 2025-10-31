from sqlalchemy import (
    Column, String, Integer, Float, Date, Boolean, TIMESTAMP,
    ForeignKey, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector
import uuid

Base = declarative_base()

# ==========================================
# CLUSTERS
# ==========================================
class Clusters(Base):
    __tablename__ = "clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    centroid = Column(Vector(384))
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))

    directions = relationship("Directions", back_populates="cluster")
    event_clusters = relationship("EventClusters", back_populates="cluster")

# ==========================================
# DIRECTIONS (belongs to one cluster)
# ==========================================
class Directions(Base):
    __tablename__ = "directions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="SET NULL"))
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))

    cluster = relationship("Clusters", back_populates="directions")
    students = relationship("Students", back_populates="direction")

# ==========================================
# STUDENTS
# ==========================================
class Students(Base):
    __tablename__ = "students"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(String, unique=True, nullable=False)
    institution = Column(String)
    direction_id = Column(UUID(as_uuid=True), ForeignKey("directions.id", ondelete="SET NULL"))
    profile_embedding = Column(Vector(768))
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))

    direction = relationship("Directions", back_populates="students")
    recommendations = relationship("Recommendations", back_populates="student")
    feedback = relationship("Feedback", back_populates="student")
    bot_user = relationship("BotUsers", back_populates="student", uselist=False)

# ==========================================
# BOT USERS (Telegram links to student)
# ==========================================
class BotUsers(Base):
    __tablename__ = "bot_users"

    telegram_id = Column(Integer, primary_key=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), unique=True)
    username = Column(String)
    last_activity = Column(TIMESTAMP, server_default=text("NOW()"))
    email = Column(String)
    is_linked = Column(Boolean, default=False)

    student = relationship("Students", back_populates="bot_user")

# ==========================================
# EVENTS
# ==========================================
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

    clusters = relationship("EventClusters", back_populates="event")
    recommendations = relationship("Recommendations", back_populates="event")

# ==========================================
# EVENT ⇄ CLUSTER (many-to-many)
# ==========================================
class EventClusters(Base):
    __tablename__ = "event_clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"))
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"))

    event = relationship("Events", back_populates="clusters")
    cluster = relationship("Clusters", back_populates="event_clusters")

# ==========================================
# RECOMMENDATIONS
# ==========================================
class Recommendations(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"))
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"))
    score = Column(Float)
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))

    student = relationship("Students", back_populates="recommendations")
    event = relationship("Events", back_populates="recommendations")

# ==========================================
# FEEDBACK
# ==========================================
class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"))
    rating = Column(Integer)
    comment = Column(String)
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))

    student = relationship("Students", back_populates="feedback")
