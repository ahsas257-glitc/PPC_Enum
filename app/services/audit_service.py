from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self) -> None:
        self.repository = AuditRepository()

    def list_recent(self, limit: int = 100, *, include_payload: bool = False) -> list[dict]:
        return self.repository.list_recent(limit, include_payload=include_payload)
