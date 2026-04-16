from contextlib import contextmanager
import logging
import threading
import time
from typing import Any, Iterator

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import get_settings

_LOGGER = logging.getLogger(__name__)
DEFAULT_CACHE_TTL_SECONDS = 1800
KEEPALIVE_INTERVAL_SECONDS = 240
_KEEPALIVE_LOCK = threading.Lock()
_KEEPALIVE_STARTED = False


def _ensure_database_optimizations(engine: Engine) -> None:
    statements = [
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users (username)",
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)",
        "CREATE INDEX IF NOT EXISTS idx_users_is_active ON users (is_active)",
        "CREATE INDEX IF NOT EXISTS idx_users_user_id ON users (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log (created_at DESC, audit_id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_projects_project_id_desc ON projects (project_id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_project_surveyors_id_desc ON project_surveyors (project_surveyor_id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_surveyors_code_lower ON surveyors (lower(surveyor_code))",
        "CREATE INDEX IF NOT EXISTS idx_surveyors_name_lower ON surveyors (lower(surveyor_name))",
        "CREATE INDEX IF NOT EXISTS idx_surveyors_tazkira_lower ON surveyors (lower(tazkira_no))",
        "CREATE INDEX IF NOT EXISTS idx_surveyors_id_desc ON surveyors (surveyor_id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_surveyors_phone_digits ON surveyors ((regexp_replace(COALESCE(phone_number, ''), '[^0-9]+', '', 'g')))",
        "CREATE INDEX IF NOT EXISTS idx_surveyors_whatsapp_digits ON surveyors ((regexp_replace(COALESCE(whatsapp_number, ''), '[^0-9]+', '', 'g')))",
        "CREATE INDEX IF NOT EXISTS idx_surveyors_code_trgm ON surveyors USING gin (surveyor_code gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS idx_surveyors_name_trgm ON surveyors USING gin (surveyor_name gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS idx_surveyors_tazkira_trgm ON surveyors USING gin (tazkira_no gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS idx_surveyor_bank_accounts_id_desc ON surveyor_bank_accounts (bank_account_id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_surveyor_bank_accounts_surveyor_id ON surveyor_bank_accounts (surveyor_id)",
        "CREATE INDEX IF NOT EXISTS idx_surveyor_bank_accounts_default ON surveyor_bank_accounts (surveyor_id, is_default)",
        "CREATE INDEX IF NOT EXISTS idx_project_surveyors_project_id ON project_surveyors (project_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_surveyors_surveyor_id ON project_surveyors (surveyor_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_surveyors_surveyor_status_dates ON project_surveyors (surveyor_id, status, start_date DESC, project_surveyor_id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_project_surveyor_provinces_ps_id ON project_surveyor_provinces (project_surveyor_id)",
        "CREATE INDEX IF NOT EXISTS idx_projects_status_project_id ON projects (status, project_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_phase_sequences_key ON project_phase_sequences (client_code, project_key, start_year)",
        "CREATE INDEX IF NOT EXISTS idx_province_sequences_code ON province_sequences (province_code)",
    ]
    for statement in statements:
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql(statement)
        except Exception as exc:  # pragma: no cover - depends on DB privileges and engine
            _LOGGER.warning("Skipping optimization statement due to database error: %s", exc)


@st.cache_resource(show_spinner=False)
def _get_engine() -> Engine:
    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=False,
        pool_recycle=900,
        pool_size=5,
        max_overflow=10,
        pool_timeout=5,
        pool_use_lifo=True,
        connect_args={
            "connect_timeout": 5,
        },
    )

    if settings.run_database_optimizations:
        _ensure_database_optimizations(engine)
    return engine


def _database_keepalive_loop() -> None:
    while True:
        try:
            with _get_engine().connect() as conn:
                conn.exec_driver_sql("SELECT 1")
        except Exception as exc:  # pragma: no cover - background health path
            _LOGGER.debug("Database keepalive skipped: %s", exc)
        time.sleep(KEEPALIVE_INTERVAL_SECONDS)


def start_database_keepalive() -> None:
    global _KEEPALIVE_STARTED
    with _KEEPALIVE_LOCK:
        if _KEEPALIVE_STARTED:
            return
        _KEEPALIVE_STARTED = True
        thread = threading.Thread(
            target=_database_keepalive_loop,
            name="database-keepalive",
            daemon=True,
        )
        thread.start()


@contextmanager
def get_connection(*, commit: bool = False) -> Iterator[Any]:
    conn = _get_engine().raw_connection()
    try:
        yield conn
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@st.cache_data(ttl=DEFAULT_CACHE_TTL_SECONDS, show_spinner=False)
def _cached_fetch_all(query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = [column[0] for column in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


@st.cache_data(ttl=DEFAULT_CACHE_TTL_SECONDS, show_spinner=False)
def _cached_fetch_one(query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            if row is None:
                return None
            columns = [column[0] for column in cur.description]
            return dict(zip(columns, row))


def clear_query_caches() -> None:
    _cached_fetch_all.clear()
    _cached_fetch_one.clear()


@contextmanager
def transaction() -> Iterator[Any]:
    with get_connection(commit=True) as conn:
        yield conn
    clear_query_caches()


def fetch_all(query: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    return _cached_fetch_all(query, params or ())


def fetch_one(query: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
    return _cached_fetch_one(query, params or ())


def execute(
    query: str,
    params: tuple[Any, ...] | None = None,
    *,
    connection: Any | None = None,
    returning: bool = False,
) -> dict[str, Any] | None:
    def _execute_in_connection(conn: Any) -> dict[str, Any] | None:
        row: dict[str, Any] | None = None
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            if returning:
                raw_row = cur.fetchone()
                if raw_row is not None:
                    columns = [column[0] for column in cur.description]
                    row = dict(zip(columns, raw_row))
        return row

    if connection is not None:
        return _execute_in_connection(connection)

    with transaction() as conn:
        return _execute_in_connection(conn)


def fetch_dataframe(query: str, params: tuple[Any, ...] | None = None) -> pd.DataFrame:
    return pd.DataFrame(fetch_all(query, params))


def table_exists(table_name: str) -> bool:
    result = fetch_one(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        ) AS exists
        """,
        (table_name,),
    )
    return bool(result and result["exists"])
