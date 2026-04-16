import logging

import streamlit as st

from app.core.auth import require_authentication
from app.core.database import start_database_keepalive
from app.core.permissions import pages_for_role, render_page
from app.core.session import get_current_user, init_session_state, logout_user
from app.design.components.cards import render_auth_intro, render_hero
from app.design.components.validation import user_friendly_error_message
from app.design.styles import inject_base_styles
from app.pages.auth.login_page import render_login_page
from app.pages.auth.register_page import render_register_page

SIDEBAR_PAGE_KEY = "sidebar_active_page"
_LOGGER = logging.getLogger(__name__)


def inject_sidebar_hover_mode() -> None:
    st.html(
        """
        <script>
        (() => {
          const doc = window.parent?.document || document;
          const body = doc.body;
          if (!body) return;

          const desktopQuery = window.matchMedia("(min-width: 769px) and (hover: hover) and (pointer: fine)");
          const syncMode = () => {
            body.classList.toggle("sidebar-hover-enabled", desktopQuery.matches);
            if (!desktopQuery.matches) return;

            const openButton =
              doc.querySelector('button[title="Open sidebar"]') ||
              doc.querySelector('button[aria-label="Open sidebar"]');
            if (openButton) {
              openButton.click();
            }
          };

          syncMode();
          if (!body.dataset.sidebarHoverBound) {
            desktopQuery.addEventListener("change", syncMode);
            body.dataset.sidebarHoverBound = "true";
          }
        })();
        </script>
        """
    )


def render_sidebar() -> str:
    current_user = get_current_user()
    available_pages = pages_for_role(current_user["role"])
    labels = [page["label"] for page in available_pages]
    sidebar_selected = st.session_state.get(SIDEBAR_PAGE_KEY)
    active_page = st.session_state.get("active_page")

    if sidebar_selected in labels:
        current_label = sidebar_selected
    elif active_page in labels:
        current_label = active_page
    else:
        current_label = labels[0]

    st.session_state["active_page"] = current_label
    if sidebar_selected not in labels:
        st.session_state[SIDEBAR_PAGE_KEY] = current_label

    st.sidebar.html(
        f"""
        <div class="sidebar-brand-card">
            <div class="sidebar-brand-eyebrow">Control Panel</div>
            <p>{current_user['full_name']}</p>
            <div class="sidebar-role-pill">{current_user['role']}</div>
        </div>
        """
    )
    selected_label = st.sidebar.radio(
        "Main navigation",
        labels,
        key=SIDEBAR_PAGE_KEY,
        label_visibility="collapsed",
        width="stretch",
    )
    if st.session_state.get("active_page") != selected_label:
        st.session_state["active_page"] = selected_label

    st.sidebar.html('<div class="sidebar-footer-label">Session</div>')
    if st.sidebar.button("Logout", width="stretch"):
        logout_user()
        st.rerun()

    return selected_label


def render_authenticated_app() -> None:
    require_authentication()
    inject_sidebar_hover_mode()
    selected_label = render_sidebar()
    render_page(selected_label)


def render_public_app() -> None:
    left_col, right_col = st.columns([0.86, 1.14], gap="medium")

    with left_col:
        render_hero(
            "Survey Management",
            "Secure access for field operations, finance, and administration.",
            kicker=None,
        )

    with right_col:
        render_auth_intro(
            "Account access",
            "Sign in or request access.",
        )
        login_tab, register_tab = st.tabs(["Login", "Register"])
        with login_tab:
            render_login_page()
        with register_tab:
            render_register_page()


def render_application_problem(exc: Exception) -> None:
    _LOGGER.exception("Unhandled Streamlit application error", exc_info=True)
    st.warning(
        user_friendly_error_message(
            exc,
            "Something interrupted this page. Refresh the page and try again. If it still happens, contact the system administrator.",
        )
    )


def main() -> None:
    st.set_page_config(
        page_title="Survey Management",
        page_icon=":material/grid_view:",
        layout="wide",
        initial_sidebar_state="auto",
        menu_items={"Get Help": None, "Report a bug": None, "About": None},
    )
    init_session_state()
    start_database_keepalive()
    authenticated = bool(get_current_user())
    inject_base_styles(authenticated=authenticated)

    if authenticated:
        try:
            render_authenticated_app()
        except Exception as exc:
            render_application_problem(exc)
    else:
        try:
            render_public_app()
        except Exception as exc:
            render_application_problem(exc)


if __name__ == "__main__":
    main()
