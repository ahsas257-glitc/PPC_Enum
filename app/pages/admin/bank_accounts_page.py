import pandas as pd
import streamlit as st

from app.core.constants import PAYMENT_TYPES
from app.core.permissions import ensure_role
from app.core.session import get_current_user
from app.design.components.cards import render_hero, render_panel_intro
from app.design.components.filters import apply_text_filter
from app.design.components.tables import render_table
from app.design.components import validation as vf
from app.repositories.bank_repository import BankRepository
from app.services.bank_account_service import BankAccountService
from app.services.surveyor_service import SurveyorService

BANK_ACCOUNT_FORM_KEY = "bank_account_form"
BANK_ACCOUNT_SURVEYOR_KEY = "bank_account_surveyor"
BANK_ACCOUNT_BANK_KEY = "bank_account_bank"
BANK_ACCOUNT_PAYMENT_TYPE_KEY = "bank_account_payment_type"
BANK_ACCOUNT_TITLE_KEY = "bank_account_title"
BANK_ACCOUNT_NUMBER_KEY = "bank_account_number"
BANK_ACCOUNT_MOBILE_KEY = "bank_account_mobile"


def render_bank_accounts_page() -> None:
    ensure_role("super_admin", "admin", "manager")
    account_service = BankAccountService()

    render_hero(
        "Payments",
        kicker="Bank Accounts",
    )
    active_view = st.radio(
        "Bank accounts view",
        ["New Account", "Account Data"],
        key="bank_accounts_active_view",
        horizontal=True,
        label_visibility="collapsed",
    )

    if active_view == "Account Data":
        render_panel_intro("Surveyors bank account list", eyebrow=None)
        accounts = pd.DataFrame(account_service.list_accounts(limit=500))
        if not accounts.empty:
            accounts = accounts[
                [
                    "surveyor_code",
                    "surveyor_name",
                    "bank_name",
                    "payment_type",
                    "account_number",
                    "mobile_number",
                    "account_title",
                    "is_default",
                    "is_active",
                ]
            ]
            accounts = apply_text_filter(accounts, "Search payment channels")
        render_table(accounts)
        return

    surveyors = SurveyorService().list_lookup(limit=1000)
    banks = BankRepository().list_all()
    surveyor_map = {f"{item['surveyor_name']} ({item['surveyor_code']})": item["surveyor_id"] for item in surveyors}
    bank_map = {item["bank_name"]: item["bank_id"] for item in banks}

    render_panel_intro("Add surveyor bank account", eyebrow=None)
    with st.form(BANK_ACCOUNT_FORM_KEY, clear_on_submit=False):
        vf.render_form_error_summary(BANK_ACCOUNT_FORM_KEY)
        col1, col2 = st.columns(2)
        with col1:
            surveyor_label = vf.selectbox(
                BANK_ACCOUNT_FORM_KEY,
                BANK_ACCOUNT_SURVEYOR_KEY,
                "Surveyor",
                list(surveyor_map.keys()) if surveyor_map else ["No surveyors"],
                required=True,
            )
            bank_label = vf.selectbox(
                BANK_ACCOUNT_FORM_KEY,
                BANK_ACCOUNT_BANK_KEY,
                "Bank",
                list(bank_map.keys()) if bank_map else ["No banks"],
                required=True,
            )
            payment_type = vf.selectbox(BANK_ACCOUNT_FORM_KEY, BANK_ACCOUNT_PAYMENT_TYPE_KEY, "Payment type", PAYMENT_TYPES, required=True)
            account_title = vf.text_input(BANK_ACCOUNT_FORM_KEY, BANK_ACCOUNT_TITLE_KEY, "Account title")
        with col2:
            account_number = vf.text_input(
                BANK_ACCOUNT_FORM_KEY,
                BANK_ACCOUNT_NUMBER_KEY,
                "Account number",
                required=payment_type == "BANK_ACCOUNT",
            )
            mobile_number = vf.text_input(
                BANK_ACCOUNT_FORM_KEY,
                BANK_ACCOUNT_MOBILE_KEY,
                "Mobile number",
                required=payment_type == "MOBILE_CREDIT",
                placeholder="+93700123456",
            )
            is_default = st.checkbox("Default account")
            is_active = st.checkbox("Active", value=True)
        submitted = st.form_submit_button("Create bank account", width="stretch")

    if submitted:
        errors = {}
        if not surveyor_map:
            errors[BANK_ACCOUNT_SURVEYOR_KEY] = "Add a surveyor first, then link the bank account."
        if not bank_map:
            errors[BANK_ACCOUNT_BANK_KEY] = "Add a bank first, then link the account."
        if errors:
            errors[vf.FORM_MESSAGE_KEY] = "Please fix the highlighted account fields."
            vf.stop_with_form_errors(BANK_ACCOUNT_FORM_KEY, errors)
        payload = {
            "surveyor_id": surveyor_map[surveyor_label],
            "bank_id": bank_map[bank_label],
            "payment_type": payment_type,
            "account_number": account_number.strip() or None,
            "mobile_number": mobile_number.strip() or None,
            "account_title": account_title.strip() or None,
            "is_default": is_default,
            "is_active": is_active,
        }
        if payment_type == "BANK_ACCOUNT" and not payload["account_number"]:
            vf.stop_with_form_errors(
                BANK_ACCOUNT_FORM_KEY,
                {
                    vf.FORM_MESSAGE_KEY: "Please add the missing payment detail.",
                    BANK_ACCOUNT_NUMBER_KEY: "Enter the bank account number for this payment type.",
                },
            )
        elif payment_type == "MOBILE_CREDIT" and not payload["mobile_number"]:
            vf.stop_with_form_errors(
                BANK_ACCOUNT_FORM_KEY,
                {
                    vf.FORM_MESSAGE_KEY: "Please add the missing payment detail.",
                    BANK_ACCOUNT_MOBILE_KEY: "Enter the mobile number for this payment type.",
                },
            )
        else:
            mobile_errors = vf.phone_errors(
                {
                    BANK_ACCOUNT_MOBILE_KEY: (
                        mobile_number,
                        "Enter a valid mobile number in international format, for example +93700123456.",
                    )
                }
            )
            if mobile_errors:
                mobile_errors[vf.FORM_MESSAGE_KEY] = "Please fix the highlighted mobile number."
                vf.stop_with_form_errors(BANK_ACCOUNT_FORM_KEY, mobile_errors)
            try:
                account_service.create_account(get_current_user(), payload)
            except Exception as exc:
                message = vf.user_friendly_error_message(
                    exc,
                    "We could not create this bank account right now. Check the account details and try again.",
                )
                vf.stop_with_form_errors(
                    BANK_ACCOUNT_FORM_KEY,
                    vf.field_errors_from_message(
                        message,
                        {
                            BANK_ACCOUNT_NUMBER_KEY: ("account number",),
                            BANK_ACCOUNT_MOBILE_KEY: ("mobile number",),
                            BANK_ACCOUNT_BANK_KEY: ("bank",),
                            BANK_ACCOUNT_SURVEYOR_KEY: ("surveyor",),
                        },
                    ),
                )
            vf.clear_form_errors(BANK_ACCOUNT_FORM_KEY)
            st.success("Bank account created.")
            st.rerun()
