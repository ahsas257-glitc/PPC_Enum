import streamlit as st

SAFE_USER_FIELDS = ("user_id", "username", "full_name", "role", "email", "is_active")


def init_session_state() -> None:
    st.session_state.setdefault("current_user", None)
    st.session_state.setdefault("active_page", None)
    st.session_state.setdefault("sidebar_active_page", None)


def sanitize_session_user(user: dict | None) -> dict | None:
    if not user:
        return None
    return {field: user.get(field) for field in SAFE_USER_FIELDS}


def login_user(user: dict) -> None:
    st.session_state["current_user"] = sanitize_session_user(user)
    st.session_state["active_page"] = None
    st.session_state["sidebar_active_page"] = None


def logout_user() -> None:
    st.session_state["current_user"] = None
    st.session_state["active_page"] = None


def get_current_user() -> dict | None:
    return st.session_state.get("current_user")
