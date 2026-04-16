import streamlit as st

from app.design.components.cards import render_panel_intro
from app.design.components import validation as vf
from app.core.session import login_user
from app.services.auth_service import AuthService

LOGIN_FORM_KEY = "login_form"
LOGIN_USERNAME_KEY = "login_username"
LOGIN_PASSWORD_KEY = "login_password"


def render_login_page() -> None:
    auth_service = AuthService()
    render_panel_intro(
        "Login",
        "Use your approved account details to enter the dashboard.",
        eyebrow=None,
    )
    with st.form(LOGIN_FORM_KEY, clear_on_submit=False):
        vf.render_form_error_summary(LOGIN_FORM_KEY)
        username = vf.text_input(
            LOGIN_FORM_KEY,
            LOGIN_USERNAME_KEY,
            "Username or email",
            required=True,
            placeholder="name@example.com",
            autocomplete="username",
        )
        password = vf.text_input(
            LOGIN_FORM_KEY,
            LOGIN_PASSWORD_KEY,
            "Password",
            required=True,
            type="password",
            placeholder="Enter your password",
            autocomplete="current-password",
        )
        submitted = st.form_submit_button("Login", type="primary", width="stretch")
    if submitted:
        errors = vf.required_errors(
            {
                LOGIN_USERNAME_KEY: (username, "Enter your username or email address."),
                LOGIN_PASSWORD_KEY: (password, "Enter your password."),
            }
        )
        if errors:
            errors[vf.FORM_MESSAGE_KEY] = "Please complete the highlighted login fields."
            vf.stop_with_form_errors(LOGIN_FORM_KEY, errors)
        try:
            with st.spinner("Signing you in..."):
                user = auth_service.login(username, password)
        except Exception as exc:
            vf.stop_with_form_errors(
                LOGIN_FORM_KEY,
                {
                    vf.FORM_MESSAGE_KEY: vf.user_friendly_error_message(
                        exc,
                        "We could not sign you in right now. Check your connection and try again.",
                    )
                },
            )
        if not user:
            message = "Check the username/email and password, then try again."
            vf.stop_with_form_errors(
                LOGIN_FORM_KEY,
                {
                    vf.FORM_MESSAGE_KEY: message,
                    LOGIN_USERNAME_KEY: message,
                    LOGIN_PASSWORD_KEY: message,
                },
            )
        if not user["is_active"]:
            st.warning("Your account exists but is still pending approval.")
            return
        vf.clear_form_errors(LOGIN_FORM_KEY)
        login_user(user)
        st.success("Login successful.")
        st.rerun()
    st.caption("Need help signing in? Contact your system administrator.")
