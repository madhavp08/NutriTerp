"""App settings.

Values come from environment variables, falling back to the repo-root .env file.
Keeping every knob in one place makes it obvious what the app depends on.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root = two levels up from this file (backend/app/config.py)
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str
    session_secret: str = "dev-only-change-me"

    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")


settings = Settings()
