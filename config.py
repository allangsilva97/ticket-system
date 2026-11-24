from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "Ticket System"
    APP_VERSION: str = "2.0.0"
    APP_URL: str = "http://localhost:8000"  # used in e-mail links
    LOG_LEVEL: str = "INFO"
    TRUSTED_PROXY_HOPS: int = 0  # trusted reverse proxies in front of the app (Vercel, Render: 1); see utils.client_ip
    APP_ENV: str = "development"  # "production" makes a weak SECRET_KEY a startup error
    # Interactive API docs (/docs, /redoc, /openapi.json). Unset: on in development, off on production and hosting platforms.
    ENABLE_DOCS: Optional[bool] = None

    # --- Security ---
    SECRET_KEY: str = "dev-secret-change-in-production-min-32-chars-long"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # --- Database ---
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'tickets.db').as_posix()}"

    # --- CORS --- comma separated (pydantic-settings would require JSON for a List)
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    # --- Pagination ---
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # --- Uploads ---
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: str = ".pdf,.png,.jpg,.jpeg,.txt,.doc,.docx,.xls,.xlsx,.zip,.csv"

    # --- E-mail (SMTP) --- leave SMTP_HOST empty to only log e-mails (dev mode)
    ENABLE_EMAIL_NOTIFICATIONS: bool = True
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_TIMEOUT: int = 30
    EMAIL_FROM: str = "noreply@ticketsystem.local"
    EMAIL_FROM_NAME: str = "Ticket System"

    # --- SLA monitor ---
    SLA_MONITOR_ENABLED: bool = True
    SLA_CHECK_INTERVAL_MINUTES: int = 15
    SLA_WARNING_THRESHOLD: float = 0.75  # warn the assignee when 75% of the SLA time is used

    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), case_sensitive=True, extra="ignore")

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_extensions_set(self) -> set:
        return {e.strip().lower() for e in self.ALLOWED_EXTENSIONS.split(",") if e.strip()}

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


settings = Settings()

def normalize_database_url(url: str) -> str:
    """Hosts such as Neon, Render and Heroku hand out postgres:// or postgresql:// URLs, which SQLAlchemy
    maps to the old psycopg2 driver. This project ships psycopg 3, so point those URLs at it."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


settings.DATABASE_URL = normalize_database_url(settings.DATABASE_URL)

# Relative sqlite paths are resolved against the project folder, not the current working dir
if settings.DATABASE_URL.startswith("sqlite:///./"):
    settings.DATABASE_URL = f"sqlite:///{(BASE_DIR / settings.DATABASE_URL[len('sqlite:///./'):]).as_posix()}"
