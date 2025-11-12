"""
Общие фикстуры для всех тестов.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from typing import Generator
import uuid
from datetime import datetime, date

# Используем тестовые модели для SQLite
from tests.test_models_sqlite import (
    TestBase as Base,
    TestStudents as Students,
    TestEvents as Events,
    TestDirections as Directions,
    TestClusters as Clusters,
    TestFavorites as Favorites,
    TestRecommendations as Recommendations,
    TestFeedback as Feedback,
    TestBotUsers as BotUsers
)
from src.api.dependencies import db_dependency
from src.api import create_app


@pytest.fixture(autouse=True)
def mock_settings():
    """Автоматически мокаем настройки во всех тестах."""
    with patch('src.core.config.settings') as mock_settings:
        mock_settings.bot_token = "test_token_123"
        mock_settings.database_url = "sqlite+aiosqlite:///./test_test.db"
        mock_settings.log_level = "DEBUG"
        mock_settings.internal_api_url = "http://localhost:8000"
        mock_settings.admin_cors_origins = ["http://localhost:5173"]
        mock_settings.sentry_dsn = None
        mock_settings.sentry_environment = "test"
        yield mock_settings


@pytest.fixture(autouse=True)
def patch_models():
    """Автоматически подменяем модели на тестовые во всех тестах."""
    from tests.test_models_sqlite import (
        TestStudents as Students,
        TestEvents as Events,
        TestBotUsers as BotUsers,
        TestFavorites as Favorites,
        TestRecommendations as Recommendations,
        TestFeedback as Feedback,
        TestDirections as Directions,
        TestClusters as Clusters
    )
    
    patches = [
        # Core models
        patch('src.core.database.models.Students', Students),
        patch('src.core.database.models.Events', Events),
        patch('src.core.database.models.BotUsers', BotUsers),
        patch('src.core.database.models.Favorites', Favorites),
        patch('src.core.database.models.Recommendations', Recommendations),
        patch('src.core.database.models.Feedback', Feedback),
        patch('src.core.database.models.Directions', Directions),
        patch('src.core.database.models.Clusters', Clusters),
        # API routes
        patch('src.api.routes.bot_users.Students', Students),
        patch('src.api.routes.bot_users.Directions', Directions),
        patch('src.api.routes.bot_users.BotUsers', BotUsers),
        patch('src.api.routes.events.Events', Events),
        patch('src.api.routes.students.Students', Students),
        patch('src.api.routes.students.Directions', Directions),
        # CRUD modules
        patch('src.core.database.crud.students.Students', Students),
        patch('src.core.database.crud.events.Events', Events),
        patch('src.core.database.crud.favorites.Favorites', Favorites),
        patch('src.core.database.crud.recommendations.Recommendations', Recommendations),
        patch('src.core.database.crud.feedback.Feedback', Feedback),
        patch('src.core.database.crud.bot_users.BotUsers', BotUsers),
        patch('src.core.database.crud.bot_users.Students', Students),
        patch('src.core.database.crud.directions.Directions', Directions),
    ]
    
    # Патчим функции, использующие NOW() для SQLite
    from datetime import datetime
    from sqlalchemy import update
    
    original_update_activity = None
    try:
        from src.core.database.crud import bot_users as bot_users_crud
        original_update_activity = bot_users_crud.update_bot_user_activity
        
        def mock_update_activity(db, telegram_id):
            """Мок для update_bot_user_activity, использующий datetime вместо NOW()."""
            stmt = (
                update(BotUsers)
                .where(BotUsers.telegram_id == telegram_id)
                .values(last_activity=datetime.now())
            )
            db.execute(stmt)
            db.commit()
        
        bot_users_crud.update_bot_user_activity = mock_update_activity
    except ImportError:
        pass
    
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()
    
    # Восстанавливаем оригинальную функцию
    if original_update_activity:
        try:
            from src.core.database.crud import bot_users as bot_users_crud
            bot_users_crud.update_bot_user_activity = original_update_activity
        except ImportError:
            pass


@pytest.fixture(scope="session")
def event_loop():
    """Фикстура для цикла событий."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_engine(patch_models):
    """Создает тестовую БД в памяти."""
    # Используем тестовые модели без Vector и NOW()
    from tests.test_models_sqlite import TestBase
    
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Создаем таблицы из тестовых моделей
    TestBase.metadata.create_all(engine)
    yield engine
    TestBase.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Создает сессию БД для тестов."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def test_client(db_session):
    """Создает тестовый клиент FastAPI."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app = create_app()
    app.dependency_overrides[db_dependency] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_cluster(db_session):
    """Создает тестовый кластер."""
    cluster = Clusters(
        id=uuid.uuid4(),
        title="Тестовый кластер",
        created_at=datetime.now()
    )
    db_session.add(cluster)
    db_session.commit()
    db_session.refresh(cluster)
    return cluster


@pytest.fixture
def sample_direction(db_session, sample_cluster):
    """Создает тестовое направление."""
    direction = Directions(
        id=uuid.uuid4(),
        title="Тестовое направление",
        cluster_id=sample_cluster.id,
        created_at=datetime.now()
    )
    db_session.add(direction)
    db_session.commit()
    db_session.refresh(direction)
    return direction


@pytest.fixture
def sample_student(db_session, sample_direction):
    """Создает тестового студента."""
    student = Students(
        id=uuid.uuid4(),
        participant_id="test_student_001",
        institution="Тестовый вуз",
        direction_id=sample_direction.id,
        created_at=datetime.now()
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return student


@pytest.fixture
def sample_event(db_session):
    """Создает тестовое мероприятие."""
    from datetime import date
    event = Events(
        id=uuid.uuid4(),
        title="Тестовое мероприятие",
        short_description="Краткое описание",
        description="Полное описание мероприятия",
        format="онлайн",
        start_date=date.today(),
        end_date=date.today(),
        link="https://example.com",
        is_active=True,
        likes_count=0,
        dislikes_count=0,
        created_at=datetime.now()
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


@pytest.fixture
def sample_bot_user(db_session, sample_student):
    """Создает тестового пользователя бота."""
    bot_user = BotUsers(
        telegram_id=123456789,
        student_id=sample_student.id,
        username="test_user",
        is_linked=True,
        last_activity=datetime.now()
    )
    db_session.add(bot_user)
    # Устанавливаем relationship вручную для тестов
    bot_user.student = sample_student
    db_session.commit()
    db_session.refresh(bot_user)
    # Убеждаемся, что relationship загружен
    db_session.refresh(bot_user, ['student'])
    return bot_user


@pytest.fixture
def mock_telegram_update():
    """Создает мок объекта Update для Telegram."""
    user = MagicMock()
    user.id = 123456789
    user.first_name = "Test"
    user.last_name = "User"
    user.username = "test_user"
    user.is_bot = False
    
    chat = MagicMock()
    chat.id = 123456789
    chat.type = "private"
    
    message = MagicMock()
    message.message_id = 1
    message.chat = chat
    message.from_user = user
    message.text = ""
    message.reply_text = AsyncMock()
    message.reply_html = AsyncMock()
    
    callback_query = MagicMock()
    callback_query.id = "test_callback_id"
    callback_query.from_user = user
    callback_query.data = ""
    callback_query.answer = AsyncMock()
    callback_query.edit_message_text = AsyncMock()
    callback_query.message = message
    
    update = MagicMock()
    update.update_id = 1
    update.message = message
    update.callback_query = None
    update.effective_user = user
    update.effective_chat = chat
    
    return update


@pytest.fixture
def mock_context():
    """Создает мок контекста для Telegram бота."""
    context = MagicMock()
    context.user_data = {}
    context.bot_data = {}
    context.chat_data = {}
    return context
