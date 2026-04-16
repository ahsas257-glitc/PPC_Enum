import streamlit as st

from app.core.exceptions import UserFacingError
from app.core.session import get_current_user, login_user
from app.design.components.cards import render_hero, render_panel_intro
from app.design.components import validation as vf
from app.services.user_service import UserService

PROFILE_FORM_KEY = "profile_form"
PROFILE_FULL_NAME_KEY = "profile_form_full_name"
PROFILE_EMAIL_KEY = "profile_form_email"


def render_profile_page() -> None:
    user = get_current_user()
    service = UserService()

    render_hero(
        "Account",
        kicker="Profile",
    )
    render_panel_intro("Profile Details", eyebrow="Edit")
    with st.form(PROFILE_FORM_KEY):
        vf.render_form_error_summary(PROFILE_FORM_KEY)
        full_name = vf.text_input(PROFILE_FORM_KEY, PROFILE_FULL_NAME_KEY, "Full name", required=True, value=user.get("full_name") or "")
        email = vf.text_input(PROFILE_FORM_KEY, PROFILE_EMAIL_KEY, "Email", required=True, value=user.get("email") or "")
        username = st.text_input("Username", value=user.get("username") or "", disabled=True)
        role = st.text_input("Role", value=user.get("role") or "", disabled=True)
        submitted = st.form_submit_button("Save profile", width="stretch")
    if submitted:
        errors = vf.required_errors(
            {
                PROFILE_FULL_NAME_KEY: (full_name, "Enter your full name."),
                PROFILE_EMAIL_KEY: (email, "Enter your email address."),
            }
        )
        errors.update(vf.email_errors({PROFILE_EMAIL_KEY: (email, "Enter a valid email address, for example name@example.com.")}))
        if errors:
            errors[vf.FORM_MESSAGE_KEY] = "Please fix the highlighted profile fields."
            vf.stop_with_form_errors(PROFILE_FORM_KEY, errors)
        try:
            updated = service.update_profile(user, full_name, email)
        except UserFacingError as exc:
            vf.stop_with_form_errors(
                PROFILE_FORM_KEY,
                vf.field_errors_from_message(str(exc), {PROFILE_EMAIL_KEY: ("email",), PROFILE_FULL_NAME_KEY: ("full name",)}),
            )
        except Exception as exc:
            message = vf.user_friendly_error_message(exc, "We could not update the profile right now. Check the highlighted fields and try again.")
            vf.stop_with_form_errors(
                PROFILE_FORM_KEY,
                vf.field_errors_from_message(message, {PROFILE_EMAIL_KEY: ("email",), PROFILE_FULL_NAME_KEY: ("full name",)}),
            )
        vf.clear_form_errors(PROFILE_FORM_KEY)
        login_user(updated)
        st.success("Profile updated.")
        st.rerun()
