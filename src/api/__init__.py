from fastapi import FastAPI

from .routes import bot_users, students, events, recommendations, feedback


def create_app() -> FastAPI:
    app = FastAPI(
        title="Internal VKR API",
        description="Внутреннее API для бота, админ-панели и фоновых сервисов",
        version="1.0.0",
    )

    app.include_router(bot_users.router, prefix="/bot", tags=["bot"])
    app.include_router(students.router, prefix="/students", tags=["students"])
    app.include_router(events.router, prefix="/events", tags=["events"])
    app.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
    app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])

    @app.get("/health", tags=["service"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

