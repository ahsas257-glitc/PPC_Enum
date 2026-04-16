from __future__ import annotations

from psycopg import errors as psycopg_errors


class UserFacingError(Exception):
    """Raised when an operation should display a clear message to end users."""


def friendly_message_for_db_error(exc: Exception) -> str | None:
    if isinstance(exc, psycopg_errors.UniqueViolation):
        diag = getattr(exc, "diag", None)
        constraint_name = (getattr(diag, "constraint_name", "") or "").lower()
        detail = (getattr(exc, "detail", "") or "").lower()
        context = f"{constraint_name} {detail} {str(exc).lower()}"

        if "users_username_key" in context or "(username)" in context:
            return "This username is already registered. Please use a different username."
        if "users_email_key" in context or "(email)" in context:
            return "This email is already registered. Please use a different email."
        if "bank_name" in context:
            return "A bank with this name already exists. Enter a different bank name."
        if "tazkira_no" in context:
            return "This tazkira number is already used. Check the number or search the surveyor first."
        if "email_address" in context:
            return "This email is already used for another surveyor. Enter a different email."
        if "whatsapp_number" in context:
            return "This WhatsApp number is already used. Enter a different WhatsApp number."
        if "phone_number" in context:
            return "This phone number is already used. Enter a different phone number."
        if "project_code" in context:
            return "A project with this generated code already exists. Change the short name, client, or start year."
        if "account_number" in context:
            return "This bank account number is already linked. Check the account number before saving."
        if "mobile_number" in context:
            return "This mobile number is already linked. Check the mobile number before saving."
        return "This value already exists in the system. Please use a different value."

    if isinstance(exc, psycopg_errors.NotNullViolation):
        return "Please fill in all required fields."

    if isinstance(exc, psycopg_errors.ForeignKeyViolation):
        return "One of the selected records is invalid. Refresh the page and try again."

    if isinstance(exc, psycopg_errors.CheckViolation):
        return "One or more entered values are invalid. Please review and try again."

    if isinstance(exc, psycopg_errors.InvalidTextRepresentation):
        return "One or more entered values have an invalid format."

    return None
