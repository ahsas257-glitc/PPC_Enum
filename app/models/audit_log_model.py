from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class AuditLog:
    audit_id: int
    actor_role: str
    actor_name: str | None
    action: str
    entity: str
    entity_key: str
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    created_at: datetime | None
