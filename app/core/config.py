"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./watchlist.db"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 43200  # 30 days
    environment: str = "development"

    brevo_api_key: str = ""
    brevo_sender_email: str = ""
    sms_enabled: bool = True

    # Deprecated: Gmail SMTP no longer used in production. Brevo HTTPS API replaces it.
    gmail_address: str = ""
    gmail_app_password: str = ""

    scheduler_enabled: bool = True
    digest_hour: int = 6
    archive_hour: int = 3


settings = Settings()
