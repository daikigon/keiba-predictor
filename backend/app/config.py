from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/keiba_db"

    # Supabase (for model storage)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_MODEL_BUCKET: str = "models"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # Scraping
    SCRAPE_INTERVAL: float = 1.5
    SCRAPE_TIMEOUT: int = 30
    SCRAPE_MAX_RETRIES: int = 3

    # Logging
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "json"  # "json" or "text"
    LOG_DIR: str = "logs"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5


settings = Settings()
