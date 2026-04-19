from app.core.audit import log_audit_event
from app.core.database import transaction
from app.repositories.bank_account_repository import BankAccountRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.surveyor_repository import SurveyorRepository


class SurveyorService:
    def __init__(self) -> None:
        self.repository = SurveyorRepository()

    def list_surveyors(self, limit: int = 500) -> list[dict]:
        return self.repository.list_all(limit=limit)

    def list_lookup(self, limit: int = 1000) -> list[dict]:
        return self.repository.list_lookup(limit=limit)

    def list_assignment_candidates(self, province_code: str | list[str] | tuple[str, ...] | None = None, limit: int = 1000) -> list[dict]:
        return self.repository.list_assignment_candidates(province_code=province_code, limit=limit)

    def list_recent_profiles(self, limit: int = 6) -> list[dict]:
        return self.repository.list_recent_profiles(limit=limit)

    def search_profiles(self, query_text: str, search_by: str = "SMART", limit: int = 12) -> list[dict]:
        return self.repository.search_profiles(query_text=query_text, search_by=search_by, limit=limit)

    def get_profile_detail(self, surveyor_id: int) -> dict | None:
        return self.repository.get_profile_detail(surveyor_id)

    def get_cv_context(self, surveyor_id: int) -> dict | None:
        profile = self.repository.get_profile_detail(surveyor_id)
        if not profile:
            return None
        return {
            "profile": profile,
            "bank_accounts": BankAccountRepository().list_for_surveyor(surveyor_id),
            "assignments": ProjectRepository().list_assignments_for_surveyor(surveyor_id, limit=200),
        }

    def create_surveyor(self, actor: dict, payload: dict) -> dict:
        province_code = payload["permanent_province_code"]
        with transaction() as conn:
            sequence = self.repository.next_sequence_for_province(province_code, connection=conn)
            payload["surveyor_code"] = f"PPC-{province_code}-{sequence:03d}"
            created = self.repository.create(payload, connection=conn)
        log_audit_event(
            actor_role=actor["role"],
            actor_name=actor["full_name"] or actor["username"],
            action="CREATE_SURVEYOR",
            entity="surveyors",
            entity_key=str(created["surveyor_id"]),
            before_json=None,
            after_json=created,
        )
        return created
