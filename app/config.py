from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGODB_URI: str = "mongodb://localhost:27017/focusforge"
    DB_NAME: str = "focusforge"
    JWT_SECRET: str = "CHANGE_ME"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days
    ENV: str = "development"
    GOOGLE_CLIENT_ID: str = ""
    OPENAI_API_KEY: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
