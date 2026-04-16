from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from html import escape
from typing import Any, TypeVar

import streamlit as st

from app.core.exceptions import UserFacingError, friendly_message_for_db_error


FORM_MESSAGE_KEY = "_form"
_FORM_ERRORS_STATE_KEY = "_app_form_field_errors"
_KEY_SAFE_PATTERN = re.compile(r"[^A-Za-z0-9_]+")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_E164_PHONE_PATTERN = re.compile(r"^\+[1-9][0-9]{7,14}$")
_TAZKIRA_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{4}-[0-9]{5}$")

_T = TypeVar("_T")


def _state() -> dict[str, dict[str, str]]:
    return st.session_state.setdefault(_FORM_ERRORS_STATE_KEY, {})


def get_form_errors(form_key: str) -> dict[str, str]:
    return dict(st.session_state.get(_FORM_ERRORS_STATE_KEY, {}).get(form_key, {}))


def clear_form_errors(form_key: str) -> None:
    forms = st.session_state.get(_FORM_ERRORS_STATE_KEY)
    if isinstance(forms, dict):
        forms.pop(form_key, None)


def set_form_errors(form_key: str, errors: Mapping[str, str]) -> None:
    clean_errors = {field_key: message for field_key, message in errors.items() if field_key and message}
    if clean_errors:
        _state()[form_key] = clean_errors
        return
    clear_form_errors(form_key)


def stop_with_form_errors(form_key: str, errors: Mapping[str, str]) -> None:
    set_form_errors(form_key, errors)
    st.rerun()


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return len(value) == 0
    return False


def required_errors(fields: Mapping[str, tuple[Any, str]]) -> dict[str, str]:
    return {field_key: message for field_key, (value, message) in fields.items() if is_blank(value)}


def email_errors(fields: Mapping[str, tuple[str, str]]) -> dict[str, str]:
    return {
        field_key: message
        for field_key, (value, message) in fields.items()
        if value and not _EMAIL_PATTERN.match(value.strip())
    }


def phone_errors(fields: Mapping[str, tuple[str, str]]) -> dict[str, str]:
    return {
        field_key: message
        for field_key, (value, message) in fields.items()
        if value and not _E164_PHONE_PATTERN.match(value.strip())
    }


def tazkira_errors(fields: Mapping[str, tuple[str, str]]) -> dict[str, str]:
    return {
        field_key: message
        for field_key, (value, message) in fields.items()
        if value and not _TAZKIRA_PATTERN.match(value.strip())
    }


def user_friendly_error_message(exc: Exception, fallback: str) -> str:
    if isinstance(exc, UserFacingError):
        return str(exc)
    return friendly_message_for_db_error(exc) or fallback


def field_errors_from_message(
    message: str,
    field_keywords: Mapping[str, Sequence[str]],
    *,
    include_form_message: bool = True,
) -> dict[str, str]:
    lowered = message.lower()
    errors = {FORM_MESSAGE_KEY: message} if include_form_message else {}
    for field_key, keywords in field_keywords.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            errors[field_key] = message
    return errors


def render_form_error_summary(
    form_key: str,
    message: str = "Please review the highlighted fields and follow the hints below.",
) -> None:
    errors = get_form_errors(form_key)
    if not errors:
        return
    st.warning(errors.get(FORM_MESSAGE_KEY) or message)


def _safe_key(value: str) -> str:
    return _KEY_SAFE_PATTERN.sub("_", value).strip("_") or "field"


def _field_error(form_key: str, field_key: str) -> str | None:
    return get_form_errors(form_key).get(field_key)


def _render_field_hint(message: str) -> None:
    st.markdown(
        f'<div class="field-error-hint">{escape(message)}</div>',
        unsafe_allow_html=True,
    )


def required_label(label: str) -> str:
    if label.endswith(" *"):
        return label
    return f"{label} *"


def _render_field(
    form_key: str,
    field_key: str,
    render_widget: Callable[[str], _T],
) -> _T:
    error = _field_error(form_key, field_key)
    container_key = f"validation_{'invalid' if error else 'field'}_{_safe_key(field_key)}"
    with st.container(key=container_key):
        value = render_widget(field_key)
        if error:
            _render_field_hint(error)
        return value


def text_input(form_key: str, field_key: str, label: str, *, required: bool = False, **kwargs: Any) -> str:
    field_label = required_label(label) if required else label
    return _render_field(
        form_key,
        field_key,
        lambda key: st.text_input(field_label, key=kwargs.pop("key", key), **kwargs),
    )


def text_area(form_key: str, field_key: str, label: str, *, required: bool = False, **kwargs: Any) -> str:
    field_label = required_label(label) if required else label
    return _render_field(
        form_key,
        field_key,
        lambda key: st.text_area(field_label, key=kwargs.pop("key", key), **kwargs),
    )


def selectbox(form_key: str, field_key: str, label: str, options: Sequence[Any], *, required: bool = False, **kwargs: Any) -> Any:
    field_label = required_label(label) if required else label
    return _render_field(
        form_key,
        field_key,
        lambda key: st.selectbox(field_label, options, key=kwargs.pop("key", key), **kwargs),
    )


def multiselect(form_key: str, field_key: str, label: str, options: Sequence[Any], *, required: bool = False, **kwargs: Any) -> list[Any]:
    field_label = required_label(label) if required else label
    return _render_field(
        form_key,
        field_key,
        lambda key: st.multiselect(field_label, options, key=kwargs.pop("key", key), **kwargs),
    )


def date_input(form_key: str, field_key: str, label: str, *, required: bool = False, **kwargs: Any) -> Any:
    field_label = required_label(label) if required else label
    return _render_field(
        form_key,
        field_key,
        lambda key: st.date_input(field_label, key=kwargs.pop("key", key), **kwargs),
    )


def file_uploader(form_key: str, field_key: str, label: str, *, required: bool = False, **kwargs: Any) -> Any:
    field_label = required_label(label) if required else label
    return _render_field(
        form_key,
        field_key,
        lambda key: st.file_uploader(field_label, key=kwargs.pop("key", key), **kwargs),
    )
