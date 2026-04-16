import pandas as pd
import streamlit as st

from app.core.constants import APPROVABLE_USER_ROLES
from app.core.permissions import ensure_role
from app.core.session import get_current_user, login_user
from app.design.components import render_stat_band
from app.design.components.cards import render_hero, render_panel_intro
from app.design.components.filters import apply_text_filter
from app.design.components.tables import render_table
from app.design.components import validation as vf
from app.services.user_service import UserService

APPROVE_USER_FORM_KEY = "approve_user_form"
APPROVE_USER_SELECTED_KEY = "approve_user_selected"
APPROVE_USER_ROLE_KEY = "approve_user_role"


def _approval_status(user: dict) -> str:
    return "Active" if user.get("is_active") else "Pending"


def _pending_option_label(user: dict) -> str:
    requested_role = str(user.get("role") or "viewer").replace("_", " ").title()
    full_name = user.get("full_name") or user.get("username") or "Unnamed user"
    email = user.get("email") or "No email"
    return f"{full_name} | {email} | requested: {requested_role}"


def _default_approved_role(user: dict) -> str:
    requested_role = user.get("role")
    if requested_role in APPROVABLE_USER_ROLES:
        return requested_role
    return "viewer"


def render_user_management_page() -> None:
    ensure_role("super_admin")
    service = UserService()
    current_user = get_current_user()

    render_hero(
        "Control",
        kicker="Users",
    )

    user_rows = service.list_users()
    total_users = len(user_rows)
    pending = [user for user in user_rows if not user["is_active"]]
    active_count = total_users - len(pending)

    render_stat_band(
        [
            ("Total users", str(total_users)),
            ("Active users", str(active_count)),
            ("Pending approval", str(len(pending))),
        ]
    )

    render_panel_intro("User List", eyebrow=None)
    users = pd.DataFrame(user_rows)
    if not users.empty:
        users["approval_status"] = users["is_active"].map(lambda value: "Active" if value else "Pending")
        users = users[
            [
                "user_id",
                "username",
                "full_name",
                "approval_status",
                "role",
                "email",
                "approved_by_name",
                "approved_at",
                "created_at",
            ]
        ]
        render_table(apply_text_filter(users, "Search users"))
    else:
        render_table(users)

    if not pending:
        st.html('<div class="users-empty-state-gap" aria-hidden="true"></div>')
        st.info("No pending users for approval.")
        return

    render_panel_intro(
        "Approvals",
        meta=f"{len(pending)} user account(s) waiting for review. Check the requested role before confirming access.",
        eyebrow="Review",
    )
    pending_map = {user["user_id"]: user for user in pending}
    pending_ids = list(pending_map.keys())
    with st.form(APPROVE_USER_FORM_KEY):
        vf.render_form_error_summary(APPROVE_USER_FORM_KEY)
        selected_user_id = vf.selectbox(
            APPROVE_USER_FORM_KEY,
            APPROVE_USER_SELECTED_KEY,
            "Pending user",
            pending_ids,
            required=True,
            format_func=lambda user_id: _pending_option_label(pending_map[user_id]),
        )
        selected_user = pending_map[selected_user_id]
        requested_role = str(selected_user.get("role") or "viewer").replace("_", " ").title()
        requested_role_default = _default_approved_role(selected_user)
        st.caption(
            f"Requested role: {requested_role} | "
            f"Email: {selected_user.get('email') or 'No email'} | "
            f"Submitted: {selected_user.get('created_at') or 'Unknown'}"
        )
        role = vf.selectbox(
            APPROVE_USER_FORM_KEY,
            APPROVE_USER_ROLE_KEY,
            "Approved role",
            APPROVABLE_USER_ROLES,
            required=True,
            index=APPROVABLE_USER_ROLES.index(requested_role_default),
        )
        submitted = st.form_submit_button("Approve user", width="stretch")
    if submitted:
        try:
            updated = service.approve_user(selected_user_id, current_user, role, True)
        except Exception as exc:
            message = vf.user_friendly_error_message(
                exc,
                "We could not approve this user right now. Refresh the list and try again.",
            )
            vf.stop_with_form_errors(
                APPROVE_USER_FORM_KEY,
                vf.field_errors_from_message(message, {APPROVE_USER_SELECTED_KEY: ("user",), APPROVE_USER_ROLE_KEY: ("role",)}),
            )
        vf.clear_form_errors(APPROVE_USER_FORM_KEY)
        if updated["user_id"] == current_user["user_id"]:
            login_user(updated)
        st.success("User approved.")
        st.rerun()
