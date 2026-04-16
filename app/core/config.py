from dataclasses import dataclass
from functools import lru_cache
import os

import streamlit as st


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_title: str = "Survey Management"
    run_database_optimizations: bool = False


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _secret_value(path: tuple[str, ...]) -> str:
    value = st.secrets
    try:
        for key in path:
            value = value[key]
    except Exception:
        return ""
    return str(value).strip()


def _resolve_database_url() -> str:
    env_url = os.environ.get("DATABASE_URL", "").strip()
    if env_url:
        return env_url

    secret_url = _secret_value(("connections", "neon_db", "url"))
    if secret_url.lower().startswith("env:"):
        secret_url = os.environ.get(secret_url[4:].strip(), "").strip()
    elif secret_url.startswith("$"):
        secret_url = os.environ.get(secret_url[1:].strip(), "").strip()
    if secret_url:
        return secret_url

    raise RuntimeError(
        "Database URL is not configured. Set DATABASE_URL in the environment or provide "
        "connections.neon_db.url in Streamlit secrets."
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    url = _resolve_database_url()
    optimize = os.environ.get("RUN_DATABASE_OPTIMIZATIONS", "").strip().lower() in {"1", "true", "yes", "on"}
    return Settings(database_url=_normalize_database_url(url), run_database_optimizations=optimize)
