from app.core.audit import log_audit_event
from app.repositories.bank_account_repository import BankAccountRepository


class BankAccountService:
    def __init__(self) -> None:
        self.repository = BankAccountRepository()

    def list_accounts(self, limit: int = 500) -> list[dict]:
        return self.repository.list_all(limit=limit)

    def list_surveyor_accounts(self, surveyor_id: int) -> list[dict]:
        return self.repository.list_for_surveyor(surveyor_id)

    def create_account(self, actor: dict, payload: dict) -> dict:
        created = self.repository.create(payload)
        log_audit_event(
            actor_role=actor["role"],
            actor_name=actor["full_name"] or actor["username"],
            action="CREATE_BANK_ACCOUNT",
            entity="surveyor_bank_accounts",
            entity_key=str(created["bank_account_id"]),
            before_json=None,
            after_json=created,
        )
        return created
