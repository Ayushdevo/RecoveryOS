from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    DATABASE_URL: str = "sqlite:///./recoveryos.db"
    ENV: str = "development"
    PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = ConfigDict(env_file=".env", extra="ignore")


settings = Settings()
