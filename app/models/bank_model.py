from dataclasses import dataclass


@dataclass(slots=True)
class Bank:
    bank_id: int
    bank_name: str
    payment_method: str
    is_active: bool
