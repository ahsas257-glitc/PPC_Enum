from datetime import date, datetime
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype
from pandas.io.formats.style import Styler
import streamlit as st


_TABLE_RENDER_INDEX = 0
_STATUS_TOKENS = ("status", "state")
_LINK_TOKENS = ("link", "url")
_DATE_SUFFIXES = ("_date", "_at")
_ACTIVE_COLUMNS = {"is_active", "active", "is_current_active"}


def _table_frame_key() -> str:
    global _TABLE_RENDER_INDEX
    _TABLE_RENDER_INDEX += 1
    return f"table_frame_{_TABLE_RENDER_INDEX}"


def _humanize_label(column_name: str) -> str:
    return str(column_name).replace("_", " ").strip().title()


def _is_link_column(column_name: str) -> bool:
    lowered = str(column_name).lower()
    return any(token in lowered for token in _LINK_TOKENS)


def _is_status_column(column_name: str) -> bool:
    lowered = str(column_name).lower()
    return any(token in lowered for token in _STATUS_TOKENS)


def _is_date_column(column_name: str, series: pd.Series) -> bool:
    lowered = str(column_name).lower()
    return is_datetime64_any_dtype(series) or lowered.endswith(_DATE_SUFFIXES)


def _format_status_text(value: object) -> object:
    if value is None or pd.isna(value):
        return ""
    return str(value).replace("_", " ").strip().title()


def _format_boolean_text(column_name: str, value: object) -> object:
    if value is None or pd.isna(value):
        return ""
    enabled = bool(value)
    lowered = str(column_name).lower()
    if lowered.startswith("has_"):
        return "Ready" if enabled else "Missing"
    if lowered == "is_current_active":
        return "Current" if enabled else "Inactive"
    if lowered in _ACTIVE_COLUMNS or lowered.startswith("is_"):
        return "Active" if enabled else "Inactive"
    return "Yes" if enabled else "No"


def _format_datetime_text(value: object) -> object:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return value


def _status_cell_style(value: object) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return ""

    palette = {
        "active": ("rgba(110, 231, 183, 0.14)", "#b7f7df", "rgba(110, 231, 183, 0.28)"),
        "approved": ("rgba(110, 231, 183, 0.14)", "#b7f7df", "rgba(110, 231, 183, 0.28)"),
        "current": ("rgba(121, 220, 255, 0.14)", "#d7f6ff", "rgba(121, 220, 255, 0.30)"),
        "ready": ("rgba(121, 220, 255, 0.14)", "#d7f6ff", "rgba(121, 220, 255, 0.30)"),
        "completed": ("rgba(110, 231, 183, 0.14)", "#b7f7df", "rgba(110, 231, 183, 0.28)"),
        "pending": ("rgba(247, 200, 115, 0.14)", "#fde7bb", "rgba(247, 200, 115, 0.28)"),
        "draft": ("rgba(247, 200, 115, 0.14)", "#fde7bb", "rgba(247, 200, 115, 0.28)"),
        "inactive": ("rgba(255, 125, 146, 0.12)", "#ffd6de", "rgba(255, 125, 146, 0.24)"),
        "missing": ("rgba(255, 125, 146, 0.12)", "#ffd6de", "rgba(255, 125, 146, 0.24)"),
        "rejected": ("rgba(255, 125, 146, 0.12)", "#ffd6de", "rgba(255, 125, 146, 0.24)"),
        "closed": ("rgba(255, 125, 146, 0.12)", "#ffd6de", "rgba(255, 125, 146, 0.24)"),
    }
    background, text, border = palette.get(
        token,
        ("rgba(106, 168, 255, 0.12)", "#dbe8ff", "rgba(106, 168, 255, 0.24)"),
    )
    return (
        f"background-color: {background}; "
        f"color: {text}; "
        f"border: 1px solid {border}; "
        "font-weight: 700; "
        "letter-spacing: 0.01em;"
    )


def _style_table(frame: pd.DataFrame) -> tuple[pd.DataFrame | Styler, dict[str, Any]]:
    display_frame = frame.copy()
    column_config: dict[str, object] = {}
    status_columns: list[str] = []
    link_columns: list[str] = []

    for column_name in display_frame.columns:
        series = display_frame[column_name]
        lowered = str(column_name).lower()
        label = _humanize_label(str(column_name))

        if is_bool_dtype(series):
            display_frame[column_name] = series.map(lambda value, name=column_name: _format_boolean_text(name, value))
            status_columns.append(column_name)
            column_config[column_name] = st.column_config.TextColumn(label=label, width="small")
            continue

        if _is_status_column(lowered):
            display_frame[column_name] = series.map(_format_status_text)
            status_columns.append(column_name)
            column_config[column_name] = st.column_config.TextColumn(label=label, width="medium")
            continue

        if _is_date_column(lowered, series):
            display_frame[column_name] = series.map(_format_datetime_text)
            column_config[column_name] = st.column_config.TextColumn(label=label, width="medium")
            continue

        if _is_link_column(lowered):
            link_columns.append(column_name)
            column_config[column_name] = st.column_config.LinkColumn(label=label, width="medium", display_text="Open")
            continue

        if pd.api.types.is_numeric_dtype(series):
            column_config[column_name] = st.column_config.NumberColumn(label=label)
            continue

        column_config[column_name] = st.column_config.TextColumn(label=label)

    if not status_columns and not link_columns:
        return display_frame, column_config

    styler = display_frame.style
    if status_columns:
        for status_column in status_columns:
            styler = styler.map(_status_cell_style, subset=[status_column])
    if link_columns:
        for link_column in link_columns:
            styler = styler.map(
                lambda value: (
                    "color: #9fe6ff; text-decoration: underline; text-decoration-color: rgba(159, 230, 255, 0.45);"
                    if value
                    else ""
                ),
                subset=[link_column],
            )
    return styler, column_config


def render_table(
    data: list[dict] | pd.DataFrame,
    *,
    width: str = "stretch",
    max_render_rows: int = 400,
    max_visible_rows: int = 10,
    row_height: int = 40,
) -> None:
    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    frame_key = _table_frame_key()

    with st.container(key=frame_key):
        if frame.empty:
            st.dataframe(frame, width=width, hide_index=True, height=112)
            return

        if len(frame) > max_render_rows:
            st.caption(
                f"Performance mode: showing first {max_render_rows:,} rows out of {len(frame):,} rows for smoother UI."
            )
            frame = frame.head(max_render_rows)

        table_data, column_config = _style_table(frame)
        visible_rows = min(max(len(frame), 1), max_visible_rows)
        table_height = 44 + (visible_rows * row_height) + 2

        st.dataframe(
            table_data,
            width=width,
            hide_index=True,
            height=table_height,
            row_height=row_height,
            column_config=column_config,
        )
