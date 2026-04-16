import pandas as pd
import streamlit as st

from app.core.constants import PAYMENT_METHODS
from app.core.permissions import ensure_role
from app.core.session import get_current_user
from app.design.components.cards import render_hero, render_panel_intro
from app.design.components.filters import apply_text_filter
from app.design.components.tables import render_table
from app.design.components import validation as vf
from app.services.bank_service import BankService

BANK_FORM_KEY = "bank_form"
BANK_NAME_KEY = "bank_form_bank_name"
BANK_PAYMENT_METHOD_KEY = "bank_form_payment_method"


def render_banks_page() -> None:
    ensure_role("super_admin", "admin")
    service = BankService()
    render_hero(
        "Payments",
        kicker="Banks",
    )

    render_panel_intro("Add New Bank", eyebrow=None)
    with st.form(BANK_FORM_KEY, clear_on_submit=False):
        vf.render_form_error_summary(BANK_FORM_KEY)
        bank_name = vf.text_input(BANK_FORM_KEY, BANK_NAME_KEY, "Bank name", required=True)
        payment_method = vf.selectbox(BANK_FORM_KEY, BANK_PAYMENT_METHOD_KEY, "Payment method", PAYMENT_METHODS, required=True)
        is_active = st.checkbox("Active", value=True)
        submitted = st.form_submit_button("Create bank", width="stretch")
    if submitted:
        errors = vf.required_errors({BANK_NAME_KEY: (bank_name, "Enter the bank name before creating it.")})
        if errors:
            errors[vf.FORM_MESSAGE_KEY] = "Please fix the highlighted bank field."
            vf.stop_with_form_errors(BANK_FORM_KEY, errors)
        try:
            service.create_bank(get_current_user(), bank_name, payment_method, is_active)
        except Exception as exc:
            message = vf.user_friendly_error_message(exc, "We could not create this bank right now. Check the bank name and try again.")
            vf.stop_with_form_errors(
                BANK_FORM_KEY,
                vf.field_errors_from_message(message, {BANK_NAME_KEY: ("bank name", "bank")}),
            )
        vf.clear_form_errors(BANK_FORM_KEY)
        st.success("Bank created.")
        st.rerun()

    render_panel_intro("Bank List", eyebrow=None)
    banks = pd.DataFrame(service.list_banks())
    if not banks.empty:
        banks = apply_text_filter(banks[["bank_id", "bank_name", "payment_method", "is_active", "created_at"]], "Search banks")
    render_table(banks)
