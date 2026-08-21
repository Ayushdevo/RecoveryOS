from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    DATABASE_URL: str = "sqlite:///./recoveryos.db"
    ENV: str = "development"
    PORT: int = 8000
    
    model_config = ConfigDict(env_file=".env", extra="ignore")

settings = Settings()
