from app.repositories.audit_repository import AuditRepository
from app.repositories.dashboard_repository import DashboardRepository


class DashboardService:
    def __init__(self) -> None:
        self.dashboard_repository = DashboardRepository()
        self.audit_repository = AuditRepository()

    def get_metrics(self) -> dict:
        return self.dashboard_repository.get_metrics()

    def get_recent_audit(self) -> list[dict]:
        return self.audit_repository.list_recent(limit=10, include_payload=False)

    def get_home_data(self) -> dict:
        return self.dashboard_repository.get_home_data()
