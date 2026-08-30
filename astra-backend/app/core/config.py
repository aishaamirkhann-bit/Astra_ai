"""
Central place for all environment-driven settings.
Har jagah os.environ.get() likhne ke bajaye, yahan se `settings` import karo.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "ASTRA AI Backend"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    SECRET_KEY: str = "dev-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    AUTH_COOKIE_NAME: str = "astra_token"
    AUTH_COOKIE_SAMESITE: str = "lax"
    AUTH_COOKIE_DOMAIN: str | None = None

    DATABASE_URL: str = "sqlite:///./astra.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    DEAL_EVENT_CHANNEL: str = "astra:deals"
    DEAL_SCAN_INTERVAL_SECONDS: int = 30
    DEAL_RESERVATION_MINUTES: int = 10

    FRONTEND_ORIGIN: str = "http://localhost:3000"

    APPROVAL_WINDOW_SECONDS: int = 30

    # --- Email OTP (2FA) ---
    OTP_LENGTH: int = 6
    OTP_EXPIRE_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 5
    OTP_TOKEN_EXPIRE_MINUTES: int = 10  # lifetime of the temp "otp_pending" token
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    CONSENT_RATE_LIMIT: int = 10
    OTP_RATE_LIMIT: int = 8

    # External authorization providers (select and configure in production).
    STT_PROVIDER: str = ""
    STT_API_KEY: str = ""
    SMS_PROVIDER: str = ""
    SMS_API_KEY: str = ""
    SMS_FROM_NUMBER: str = ""

    # --- SMTP (real email) ---
    # Fill these in .env — never commit real credentials.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@astra.ai"
    SMTP_FROM_NAME: str = "ASTRA AI"
    SMTP_USE_TLS: bool = True
    # When true (dev only), OTP is also printed to the server console/logs
    # so you can test without waiting on real email delivery.
    OTP_DEBUG_LOG: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
