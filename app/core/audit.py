from typing import Any

from app.repositories.audit_repository import AuditRepository


def log_audit_event(
    actor_role: str,
    actor_name: str,
    action: str,
    entity: str,
    entity_key: str,
    before_json: dict[str, Any] | None = None,
    after_json: dict[str, Any] | None = None,
) -> None:
    AuditRepository().create(
        actor_role=actor_role,
        actor_name=actor_name,
        action=action,
        entity=entity,
        entity_key=entity_key,
        before_json=before_json,
        after_json=after_json,
    )
