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

          const SIDEBAR_HOVER_VERSION = "2026-04-sidebar-v2";
          const desktopQuery = window.matchMedia("(min-width: 769px) and (hover: hover) and (pointer: fine)");
          const AUTO_CLOSE_MS = 90;
          const EDGE_OPEN_PX = 34;
          const closeSelectors = [
            'button[title="Close sidebar"]',
            'button[aria-label="Close sidebar"]',
            '[data-testid="stSidebarCollapseButton"]'
          ];

          const sidebarElement = () => doc.querySelector('[data-testid="stSidebar"]');

          const openAutoSidebar = () => {
            if (!desktopQuery.matches) return;
            body.classList.remove("sidebar-force-collapsed");
            body.classList.remove("sidebar-auto-hidden");
            body.classList.add("sidebar-auto-open");
            window.clearTimeout(body.__sidebarAutoTimer);
          };

          const closeAutoSidebar = (blurActive = false) => {
            const activeElement = doc.activeElement;
            if (blurActive && activeElement && typeof activeElement.blur === "function") {
              activeElement.blur();
            }

            body.classList.add("sidebar-force-collapsed");
            body.classList.add("sidebar-auto-hidden");
            body.classList.remove("sidebar-auto-open");
            window.clearTimeout(body.__sidebarAutoTimer);
          };

          const sidebarHasFocus = () => {
            const sidebar = sidebarElement();
            const activeElement = doc.activeElement;
            return Boolean(sidebar && activeElement && sidebar.contains(activeElement));
          };

          const scheduleAutoClose = (delay = AUTO_CLOSE_MS) => {
            if (!desktopQuery.matches) return;
            window.clearTimeout(body.__sidebarAutoTimer);
            body.__sidebarAutoTimer = window.setTimeout(() => {
              const sidebar = sidebarElement();
              const isHovered = sidebar && sidebar.matches(":hover");
              if (!sidebarHasFocus() && !isHovered) {
                closeAutoSidebar();
              }
            }, delay);
          };

          const pointerInsideSidebar = (event) => {
            const sidebar = sidebarElement();
            if (!sidebar) return false;
            if (sidebar.contains(event.target)) return true;
            const rect = sidebar.getBoundingClientRect();
            return (
              event.clientX >= rect.left &&
              event.clientX <= rect.right &&
              event.clientY >= rect.top &&
              event.clientY <= rect.bottom
            );
          };

          const forceSidebarClosed = () => {
            closeAutoSidebar(true);
            window.clearTimeout(body.__sidebarForceTimer);
            body.__sidebarForceTimer = window.setTimeout(() => {
              if (!desktopQuery.matches) {
                body.classList.remove("sidebar-force-collapsed");
                body.classList.remove("sidebar-auto-hidden");
                body.classList.remove("sidebar-auto-open");
              }
            }, 520);

            if (!desktopQuery.matches) {
              window.setTimeout(() => {
                const closeButton = closeSelectors
                  .map((selector) => doc.querySelector(selector))
                  .find(Boolean);
                if (closeButton) {
                  closeButton.click();
                }
              }, 90);
            }
          };

          const bindSidebarElement = () => {
            const sidebar = sidebarElement();
            if (!sidebar || sidebar.dataset.autoHoverBound === "true") return;
            sidebar.dataset.autoHoverBound = "true";
            sidebar.addEventListener("pointerenter", openAutoSidebar, { passive: true });
            sidebar.addEventListener("mouseenter", openAutoSidebar, { passive: true });
            sidebar.addEventListener("pointerleave", () => scheduleAutoClose(70), { passive: true });
            sidebar.addEventListener("mouseleave", () => scheduleAutoClose(70), { passive: true });
          };

          const syncMode = () => {
            body.classList.toggle("sidebar-hover-enabled", desktopQuery.matches);
            if (!desktopQuery.matches) {
              body.classList.remove("sidebar-force-collapsed");
              body.classList.remove("sidebar-auto-hidden");
              body.classList.remove("sidebar-auto-open");
              return;
            }

            const openButton =
              doc.querySelector('button[title="Open sidebar"]') ||
              doc.querySelector('button[aria-label="Open sidebar"]');
            if (openButton) {
              openButton.click();
            }
            bindSidebarElement();
            window.requestAnimationFrame(bindSidebarElement);
            closeAutoSidebar();
          };

          syncMode();
          if (body.dataset.sidebarHoverBound !== SIDEBAR_HOVER_VERSION) {
            if (body.__sidebarHoverObserver) {
              body.__sidebarHoverObserver.disconnect();
            }
            desktopQuery.addEventListener("change", syncMode);
            doc.addEventListener("change", (event) => {
              const sidebar = doc.querySelector('[data-testid="stSidebar"]');
              if (!sidebar || !sidebar.contains(event.target)) return;
              const radio = event.target.closest?.('[data-testid="stRadio"]');
              if (radio) {
                forceSidebarClosed();
              }
            }, true);
            doc.addEventListener("click", (event) => {
              const sidebar = sidebarElement();
              if (!sidebar || !sidebar.contains(event.target)) return;
              const navLabel = event.target.closest?.('[data-testid="stRadio"] label');
              if (navLabel) {
                window.setTimeout(forceSidebarClosed, 120);
              }
            }, true);
            doc.addEventListener("pointerenter", (event) => {
              if (!desktopQuery.matches || !pointerInsideSidebar(event)) return;
              openAutoSidebar();
            }, true);
            doc.addEventListener("pointermove", (event) => {
              if (!desktopQuery.matches) return;
              const sidebar = sidebarElement();
              if (pointerInsideSidebar(event)) {
                openAutoSidebar();
                return;
              }
              if (event.clientX <= EDGE_OPEN_PX) {
                openAutoSidebar();
                return;
              }
              if (body.classList.contains("sidebar-auto-open") && sidebar) {
                const rect = sidebar.getBoundingClientRect();
                if (event.clientX > rect.right + 4 || event.clientY < rect.top || event.clientY > rect.bottom) {
                  scheduleAutoClose(70);
                }
              }
            }, { passive: true });
            doc.addEventListener("pointerleave", (event) => {
              if (!desktopQuery.matches || !pointerInsideSidebar(event)) return;
              scheduleAutoClose(70);
            }, true);
            doc.addEventListener("focusin", (event) => {
              const sidebar = sidebarElement();
              if (!desktopQuery.matches || !sidebar || !sidebar.contains(event.target)) return;
              openAutoSidebar();
            }, true);
            doc.addEventListener("keydown", (event) => {
              if (event.key === "Escape") {
                forceSidebarClosed();
              }
            }, true);
            body.__sidebarHoverObserver = new MutationObserver(bindSidebarElement);
            body.__sidebarHoverObserver.observe(body, { childList: true, subtree: true });
            body.dataset.sidebarHoverBound = SIDEBAR_HOVER_VERSION;
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
    authenticated = bool(get_current_user())
    if authenticated:
        start_database_keepalive()
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
