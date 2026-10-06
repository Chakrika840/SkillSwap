"""
All settings in one place, read from environment variables (or a .env file).
Same idea as Spring Boot's application.properties with ${ENV_VAR:default} placeholders.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
load_dotenv(BASE_DIR / ".env")                              # local runs; Docker passes env vars directly


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # ---------- database ----------
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'skillswap.db'}")

    # ---------- JWT ----------
    jwt_secret: str = os.getenv("JWT_SECRET", "skillswap-dev-secret-change-me-0123456789abcdefghijklmnop")
    jwt_expiration_minutes: int = int(os.getenv("JWT_EXPIRATION_MINUTES", str(24 * 60)))   # 24 hours

    # ---------- CORS (only needed when the frontend runs on a different origin) ----------
    cors_origins: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if o.strip()
    ]

    # ---------- local time zone for session times ----------
    timezone: str = os.getenv("APP_TIMEZONE", "Asia/Kolkata")

    # ---------- seed data ----------
    admin_email: str = os.getenv("ADMIN_EMAIL", "admin@skillswap.com")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")
    seed_demo_users: bool = _bool("SEED_DEMO_USERS", True)

    # ---------- Groq LLM (AI skill test) ----------
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    groq_fallback_model: str = os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b").strip()
    groq_timeout_seconds: float = float(os.getenv("GROQ_TIMEOUT_SECONDS", "60"))


settings = Settings()

if len(settings.jwt_secret) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters long")
