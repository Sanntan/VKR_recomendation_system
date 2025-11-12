from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError

from src.core.config import settings
from src.core.logging_config import setup_logging, get_logger
from src.core.exceptions import BaseAppException
from src.core.sentry_config import init_sentry
from .routes import bot_users, students, events, recommendations, feedback, favorites, maintenance
from .middleware.error_handler import (
    base_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    sqlalchemy_exception_handler,
    general_exception_handler,
)

# Настройка логирования
setup_logging(
    level=settings.log_level,
    service_name="vkr.api"
)
logger = get_logger(__name__)

# Инициализация Sentry
init_sentry()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Internal VKR API",
        description="Внутреннее API для бота, админ-панели и фоновых сервисов",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.admin_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Регистрация обработчиков ошибок
    app.add_exception_handler(BaseAppException, base_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    app.include_router(bot_users.router, prefix="/bot", tags=["bot"])
    app.include_router(students.router, prefix="/students", tags=["students"])
    app.include_router(events.router, prefix="/events", tags=["events"])
    app.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
    app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
    app.include_router(favorites.router, prefix="/favorites", tags=["favorites"])
    app.include_router(maintenance.router, prefix="/maintenance", tags=["maintenance"])

    @app.get("/health", tags=["service"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    logger.info("FastAPI приложение создано и настроено")
    return app


app = create_app()

