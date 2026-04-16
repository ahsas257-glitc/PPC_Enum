import streamlit as st

from app.core.session import get_current_user


def require_authentication() -> dict:
    current_user = get_current_user()
    if not current_user:
        st.warning("Please log in to continue.")
        st.stop()
    return current_user
