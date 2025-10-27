from pydantic_settings import BaseSettings
import os
from typing import Optional

class Settings(BaseSettings):
    bot_token: Optional[str] = None
    database_url: str = "sqlite+aiosqlite:///./test.db"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.bot_token:
            raise ValueError("BOT_TOKEN не найден! Создайте файл .env или установите переменную окружения")

settings = Settings()