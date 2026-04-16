from app.core.audit import log_audit_event
from app.repositories.bank_repository import BankRepository


class BankService:
    def __init__(self) -> None:
        self.repository = BankRepository()

    def list_banks(self) -> list[dict]:
        return self.repository.list_all()

    def create_bank(self, actor: dict, bank_name: str, payment_method: str, is_active: bool) -> dict:
        created = self.repository.create(bank_name.strip(), payment_method, is_active)
        log_audit_event(
            actor_role=actor["role"],
            actor_name=actor["full_name"] or actor["username"],
            action="CREATE_BANK",
            entity="banks",
            entity_key=str(created["bank_id"]),
            before_json=None,
            after_json=created,
        )
        return created
