import streamlit as st

from app.core.exceptions import UserFacingError
from app.design.components.cards import render_panel_intro
from app.design.components import validation as vf
from app.services.auth_service import AuthService

REGISTER_FORM_KEY = "register_form"
REGISTER_FULL_NAME_KEY = "register_full_name"
REGISTER_USERNAME_KEY = "register_username"
REGISTER_EMAIL_KEY = "register_email"
REGISTER_PASSWORD_KEY = "register_password"
REGISTER_ROLE_KEY = "register_role"


def render_register_page() -> None:
    auth_service = AuthService()
    render_panel_intro(
        "Register",
        "Create an access request. A super admin must approve it before you can sign in.",
        eyebrow=None,
    )
    with st.form(REGISTER_FORM_KEY, clear_on_submit=False):
        vf.render_form_error_summary(REGISTER_FORM_KEY)
        full_name = vf.text_input(
            REGISTER_FORM_KEY,
            REGISTER_FULL_NAME_KEY,
            "Full name",
            required=True,
            placeholder="Your full name",
            autocomplete="name",
        )
        username = vf.text_input(
            REGISTER_FORM_KEY,
            REGISTER_USERNAME_KEY,
            "Username / email",
            required=True,
            placeholder="name@example.com",
            autocomplete="username",
        )
        email = vf.text_input(
            REGISTER_FORM_KEY,
            REGISTER_EMAIL_KEY,
            "Email",
            required=True,
            placeholder="name@example.com",
            autocomplete="email",
        )
        password = vf.text_input(
            REGISTER_FORM_KEY,
            REGISTER_PASSWORD_KEY,
            "Password",
            required=True,
            type="password",
            placeholder="Create a password",
            autocomplete="new-password",
        )
        role = vf.selectbox(
            REGISTER_FORM_KEY,
            REGISTER_ROLE_KEY,
            "Requested role",
            ["viewer", "manager", "admin"],
            required=True,
            help="Choose the level of access you need.",
        )
        submitted = st.form_submit_button("Create account", type="primary", width="stretch")
    if submitted:
        errors = vf.required_errors(
            {
                REGISTER_FULL_NAME_KEY: (full_name, "Enter your full name."),
                REGISTER_USERNAME_KEY: (username, "Enter the username you will use to sign in."),
                REGISTER_EMAIL_KEY: (email, "Enter your email address."),
                REGISTER_PASSWORD_KEY: (password, "Create a password before submitting."),
            }
        )
        errors.update(vf.email_errors({REGISTER_EMAIL_KEY: (email, "Enter a valid email address, for example name@example.com.")}))
        if password and len(password) < 8:
            errors[REGISTER_PASSWORD_KEY] = "Use at least 8 characters for the password."
        if errors:
            errors[vf.FORM_MESSAGE_KEY] = "Please fix the highlighted account request fields."
            vf.stop_with_form_errors(REGISTER_FORM_KEY, errors)
        try:
            with st.spinner("Submitting your account request..."):
                auth_service.register(full_name, username, email, password, role)
        except UserFacingError as exc:
            errors = vf.field_errors_from_message(
                str(exc),
                {
                    REGISTER_USERNAME_KEY: ("username",),
                    REGISTER_EMAIL_KEY: ("email",),
                },
            )
            vf.stop_with_form_errors(REGISTER_FORM_KEY, errors)
        except Exception as exc:
            vf.stop_with_form_errors(
                REGISTER_FORM_KEY,
                {
                    vf.FORM_MESSAGE_KEY: vf.user_friendly_error_message(
                        exc,
                        "We could not create the account right now. Check your information and try again.",
                    )
                },
            )
        vf.clear_form_errors(REGISTER_FORM_KEY)
        st.success("Account created. A super admin can now approve it.")
    st.caption("Approval is required before a new account can sign in.")
