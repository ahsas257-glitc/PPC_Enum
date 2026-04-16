from dataclasses import dataclass


@dataclass(slots=True)
class BankAccount:
    bank_account_id: int
    surveyor_id: int
    bank_id: int
    payment_type: str
    account_number: str | None
    mobile_number: str | None
    account_title: str | None
    is_default: bool
    is_active: bool
