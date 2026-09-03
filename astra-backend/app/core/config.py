"""
Central place for all environment-driven settings.
Har jagah os.environ.get() likhne ke bajaye, yahan se `settings` import karo.
"""
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "dev-secret-change-me"


class Settings(BaseSettings):
    APP_NAME: str = "ASTRA AI Backend"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    # "json" = one JSON object per line (observability-friendly), "text" = dev readable.
    LOG_FORMAT: str = ""

    SECRET_KEY: str = DEFAULT_SECRET_KEY
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

    # --- Live market-price feed (USD→PKR reference for import-priced items) ---
    MARKET_FEED_ENABLED: bool = True
    MARKET_FEED_URL: str = "https://open.er-api.com/v6/latest/USD"
    MARKET_FEED_TTL_SECONDS: int = 3600
    MARKET_OBSERVATION_INTERVAL_HOURS: int = 6
    MARKET_BASELINE_USD_PKR: float = 278.5

    # --- Live product catalog providers ---
    EBAY_CLIENT_ID: str = ""
    EBAY_CLIENT_SECRET: str = ""
    RAPIDAPI_KEY: str = ""
    RAPIDAPI_HOST: str = "real-time-product-search.p.rapidapi.com"
    PRODUCT_PROVIDER_TIMEOUT_SECONDS: float = 5.0
    REFRESH_PRODUCTS_ON_STARTUP: bool = True

    # --- Card payments (Stripe). Empty keys = wallet-only rails. ---
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    FRONTEND_ORIGIN: str = "http://localhost:3000"

    APPROVAL_WINDOW_SECONDS: int = 30
    CHECKOUT_SESSION_TTL_SECONDS: int = 600

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

    # --- Text-to-speech (spoken replies). Empty PROVIDER = feature disabled, no 500s. ---
    TTS_PROVIDER: str = ""
    TTS_API_KEY: str = ""
    TTS_VOICE: str = ""
    TTS_MODEL: str = ""
    TTS_TIMEOUT_SECONDS: float = 8.0

    # --- Vision (image understanding for multimodal search). Same empty-key discipline. ---
    VISION_PROVIDER: str = ""
    VISION_API_KEY: str = ""
    VISION_MODEL: str = ""
    VISION_TIMEOUT_SECONDS: float = 8.0

    # --- Multimodal fusion weights (text vs. voice-transcript vs. image labels). ---
    FUSION_TEXT_WEIGHT: float = 1.0
    FUSION_IMAGE_WEIGHT: float = 0.7
    FUSION_VOICE_WEIGHT: float = 0.9

    # Optional AI seller-agent provider. Rules remain the safe fallback.
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_TIMEOUT_SECONDS: float = 8.0

    # --- SMTP (real email) ---
    # Fill these in .env — never commit real credentials.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_USER: str = ""  # alias accepted by some providers; SMTP_USERNAME wins
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@astra.ai"
    SMTP_FROM_NAME: str = "ASTRA AI"
    SMTP_USE_TLS: bool = True
    # --- Resend (alternative provider; wins over SMTP when set) ---
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "ASTRA AI <onboarding@resend.dev>"
    # When true (dev only), OTP is also printed to the server console/logs
    # so you can test without waiting on real email delivery.
    OTP_DEBUG_LOG: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> "Settings":
        if self.APP_ENV == "production":
            if self.SECRET_KEY == DEFAULT_SECRET_KEY:
                raise RuntimeError(
                    "SECRET_KEY is still the dev default — set a strong SECRET_KEY "
                    "before running with APP_ENV=production."
                )
            self.APP_DEBUG = False
            self.OTP_DEBUG_LOG = False
            if self.STRIPE_SECRET_KEY and not self.STRIPE_WEBHOOK_SECRET:
                raise RuntimeError(
                    "STRIPE_SECRET_KEY is set but STRIPE_WEBHOOK_SECRET is missing — "
                    "card top-ups could never settle in production."
                )
        if not self.LOG_FORMAT:
            self.LOG_FORMAT = "json" if self.APP_ENV == "production" else "text"
        return self


settings = Settings()
