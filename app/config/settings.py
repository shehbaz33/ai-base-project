from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # Application
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_NAME: str = os.getenv("APP_NAME", "FastAPI Skeleton")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15))
    print(ACCESS_TOKEN_EXPIRE_MINUTES,'ACCESS_TOKEN_EXPIRE_MINUTES')
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30))

    # Database
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "postgres")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "vectordb")
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Celery & Redis
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

    # External APIs
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields from .env file
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
