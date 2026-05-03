"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./rmb_restock.db"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 43200  # 30 days
    resend_api_key: str = ""
    notification_from_email: str = "restock@example.com"
    environment: str = "development"


settings = Settings()
