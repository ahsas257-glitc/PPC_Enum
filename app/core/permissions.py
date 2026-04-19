from functools import lru_cache
from importlib import import_module

import streamlit as st


PAGE_ORDER = [
    "Search & Reports",
    "Dashboard",
    "Projects",
    "Surveyors",
    "CV Generator",
    "Banks",
    "Bank Accounts",
    "Users",
    "Audit Logs",
    "Profile",
]

PAGE_REGISTRY = {
    "Dashboard": {
        "label": "Dashboard",
        "roles": {"super_admin", "admin", "manager", "viewer"},
        "module": "app.pages.shared.dashboard_home",
        "renderer_name": "render_dashboard_page",
    },
    "Projects": {
        "label": "Projects",
        "roles": {"super_admin", "admin", "manager"},
        "module": "app.pages.admin.projects_page",
        "renderer_name": "render_projects_page",
    },
    "Surveyors": {
        "label": "Surveyors",
        "roles": {"super_admin", "admin", "manager"},
        "module": "app.pages.admin.surveyors_page",
        "renderer_name": "render_surveyors_page",
    },
    "CV Generator": {
        "label": "CV Generator",
        "roles": {"super_admin", "admin", "manager"},
        "module": "app.pages.admin.cv_generator_page",
        "renderer_name": "render_cv_generator_page",
    },
    "Search & Reports": {
        "label": "Search & Reports",
        "roles": {"super_admin", "admin", "manager"},
        "module": "app.pages.admin.search_reports_page",
        "renderer_name": "render_search_reports_page",
    },
    "Banks": {
        "label": "Banks",
        "roles": {"super_admin", "admin"},
        "module": "app.pages.admin.banks_page",
        "renderer_name": "render_banks_page",
    },
    "Bank Accounts": {
        "label": "Bank Accounts",
        "roles": {"super_admin", "admin", "manager"},
        "module": "app.pages.admin.bank_accounts_page",
        "renderer_name": "render_bank_accounts_page",
    },
    "Users": {
        "label": "Users",
        "roles": {"super_admin"},
        "module": "app.pages.owner.user_management_page",
        "renderer_name": "render_user_management_page",
    },
    "Audit Logs": {
        "label": "Audit Logs",
        "roles": {"super_admin"},
        "module": "app.pages.owner.audit_logs_page",
        "renderer_name": "render_audit_logs_page",
    },
    "Profile": {
        "label": "Profile",
        "roles": {"super_admin", "admin", "manager", "viewer"},
        "module": "app.pages.shared.profile_page",
        "renderer_name": "render_profile_page",
    },
}


def pages_for_role(role: str) -> list[dict]:
    available = [name for name in PAGE_ORDER if name in PAGE_REGISTRY and role in PAGE_REGISTRY[name]["roles"]]
    return [PAGE_REGISTRY[name] for name in available]


@lru_cache(maxsize=None)
def _resolve_renderer(label: str):
    page = PAGE_REGISTRY[label]
    module = import_module(page["module"])
    return getattr(module, page["renderer_name"])


def render_page(label: str) -> None:
    _resolve_renderer(label)()


def ensure_role(*allowed_roles: str) -> None:
    current_user = st.session_state.get("current_user")
    if not current_user or current_user["role"] not in allowed_roles:
        st.warning("You do not have access to this page. Ask a super admin to update your role if you need it.")
        st.stop()
