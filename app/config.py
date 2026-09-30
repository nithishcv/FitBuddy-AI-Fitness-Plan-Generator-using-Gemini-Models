import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root
BASE_DIR = Path(__file__).resolve().parent.parent


# Load .env if it exists
load_dotenv(BASE_DIR / ".env")


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"

AVAILABLE_GEMINI_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-omni-1.1-flash",
]


def _resolve_model_name(env_name: str, default: str) -> str:
    """Return the configured model value, keeping 'auto' as the app setting."""

    value = os.getenv(env_name, default).strip()

    if not value:
        return default

    normalized = value.lower()

    if normalized == "auto":
        return DEFAULT_GEMINI_MODEL

    if normalized in {model.lower() for model in AVAILABLE_GEMINI_MODELS}:
        return value

    return DEFAULT_GEMINI_MODEL


def resolve_runtime_model(model_name: str) -> str:
    """Convert the configured app value into a valid Gemini API model name."""

    if not model_name or model_name.lower() == "auto":
        return DEFAULT_GEMINI_MODEL

    normalized = model_name.lower()

    if normalized in {model.lower() for model in AVAILABLE_GEMINI_MODELS}:
        return model_name

    return DEFAULT_GEMINI_MODEL


class Settings(BaseSettings):
    """
    Application configuration.

    Values are loaded from environment variables and .env.
    """

    app_name: str = "FitBuddy"

    database_url: str = "sqlite:///./fitbuddy.db"

    gemini_api_key: str = ""

    workout_model: str = "gemini-3.5-flash-lite"

    nutrition_model: str = "gemini-3.5-flash-lite"

    admin_key: str = ""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


def _load_settings() -> Settings:
    """
    Load settings while supporting the exact environment
    variable names used by this project.
    """

    api_key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or ""
    ).strip()

    return Settings(
        app_name=os.getenv(
            "APP_NAME",
            "FitBuddy",
        ),
        database_url=os.getenv(
            "DATABASE_URL",
            "sqlite:///./fitbuddy.db",
        ),
        gemini_api_key=api_key,
        workout_model=_resolve_model_name(
            "FITBUDDY_WORKOUT_MODEL",
            DEFAULT_GEMINI_MODEL,
        ),
        nutrition_model=_resolve_model_name(
            "FITBUDDY_NUTRITION_MODEL",
            DEFAULT_GEMINI_MODEL,
        ),
        admin_key=os.getenv(
            "ADMIN_KEY",
            "",
        ),
    )


def get_settings() -> Settings:
    """
    Return application settings using the current environment values.
    """

    return _load_settings()