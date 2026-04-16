import re

from app.core.audit import log_audit_event
from app.core.database import transaction
from app.repositories.project_repository import ProjectRepository


def _slug(value: str, fallback: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", (value or "").upper())
    if not parts:
        return fallback
    if len(parts) == 1:
        return parts[0][:12]
    return "".join(part[0] for part in parts[:4])


class ProjectService:
    def __init__(self) -> None:
        self.repository = ProjectRepository()

    def list_projects(self, limit: int = 500) -> list[dict]:
        return self.repository.list_all(limit=limit)

    def list_assignments(self, limit: int = 500) -> list[dict]:
        return self.repository.list_assignments(limit=limit)

    def list_assignments_for_surveyor(self, surveyor_id: int, limit: int = 500) -> list[dict]:
        return self.repository.list_assignments_for_surveyor(surveyor_id, limit=limit)

    def list_assignment_conflicts(
        self,
        project_id: int,
        surveyor_ids: list[int],
        start_date,
        end_date,
        limit: int = 500,
    ) -> list[dict]:
        return self.repository.list_assignment_conflicts(
            project_id=project_id,
            surveyor_ids=surveyor_ids,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    def create_project(self, actor: dict, payload: dict) -> dict:
        client_code = _slug(payload["client_name"], "GEN")
        project_key = payload["project_short_name"] or _slug(payload["project_name"], "PROJECT")
        start_year = payload["start_date"].year if payload.get("start_date") else None
        with transaction() as conn:
            next_phase = self.repository.reserve_next_phase_sequence(client_code, project_key, start_year, connection=conn)
            payload["phase_number"] = next_phase
            payload["project_code"] = f"{client_code}-{project_key}-P{next_phase:02d}"
            payload["project_short_name"] = project_key
            created = self.repository.create(payload, connection=conn)
        log_audit_event(
            actor_role=actor["role"],
            actor_name=actor["full_name"] or actor["username"],
            action="CREATE_PROJECT",
            entity="projects",
            entity_key=str(created["project_id"]),
            before_json=None,
            after_json=created,
        )
        return created

    def create_assignment(self, actor: dict, payload: dict) -> dict:
        created = self.create_assignments(actor, [payload])
        return created[0]

    def create_assignments(self, actor: dict, payloads: list[dict]) -> list[dict]:
        created_assignments = self.repository.create_assignments(payloads)
        actor_name = actor["full_name"] or actor["username"]
        for created in created_assignments:
            log_audit_event(
                actor_role=actor["role"],
                actor_name=actor_name,
                action="ASSIGN_SURVEYOR",
                entity="project_surveyors",
                entity_key=str(created["project_surveyor_id"]),
                before_json=None,
                after_json=created,
            )
        return created_assignments
