"""Configuration. Values come from the environment with development defaults."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings:
    app_name: str = "CogniPath AI"
    version: str = "1.0.0"
    database_path: Path = Path(os.getenv("COGNIPATH_DB", BASE_DIR / "cognipath.db"))
    model_path: Path = Path(
        os.getenv("COGNIPATH_MODELS", BASE_DIR / "models" / "cognipath_models.joblib")
    )
    # Development default only. In any real deployment this MUST come from the
    # environment; the app logs a warning when the fallback is used.
    jwt_secret: str = os.getenv("COGNIPATH_SECRET", "dev-only-insecure-secret-change-me")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = int(os.getenv("COGNIPATH_TOKEN_MINUTES", "480"))
    demo_cohort_size: int = int(os.getenv("COGNIPATH_DEMO_SIZE", "60"))
    cors_origins: list[str] = os.getenv(
        "COGNIPATH_CORS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")

    @property
    def using_default_secret(self) -> bool:
        return os.getenv("COGNIPATH_SECRET") is None


settings = Settings()
