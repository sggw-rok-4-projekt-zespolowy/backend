from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # All of the settings here are defaults for when .env is not accessible.
    # .env and ENV variables take precedence over these definitions

    # Application
    APP_NAME: str = "Backend"
    DEBUG: bool = False
    ADMIN_EMAIL: str = "admin@admin"
    ADMIN_USERNAME: str = "administrator"
    ADMIN_PASSWORD: str = "insecure"

    # Database
    DATABASE_URL: str = "sqlite:///./database.db"

    # JWT Settings
    JWT_SECRET_KEY: str = "super-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    FRONTEND_URL: str = "http://localhost:5173"

    # Cookie settings
    COOKIE_SECURE: bool = False  # Set to True in production (HTTPS)
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_HTTPONLY: bool = True

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }

    # Audio upload directory
    UPLOAD_DIR: str = "storage"

    # Public base URL (used to build audio preview URLs)
    BASE_URL: str = "http://127.0.0.1:8000"

    # How long the session will remain available (minutes) after successful matchmaking, but before all players connected.
    REGISTERED_SESSION_START_TIMEOUT: int = 1

    # How long before session is finished when one of the player disconnects when session is in progress. In seconds.
    SESSION_DISCONNECT_TERMINATION_TIME: int = 45


settings = Settings()
