from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGODB_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "focusforge"
    JWT_SECRET: str = "focusforge-super-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours instead of 30 minutes
    ENV: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()
