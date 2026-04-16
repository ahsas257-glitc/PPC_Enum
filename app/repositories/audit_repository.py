from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.core.database import execute, fetch_all
from psycopg.types.json import Jsonb


def _json_compatible(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"type": "binary", "size": len(value)}
    return value


class AuditRepository:
    def list_recent(self, limit: int = 100, *, include_payload: bool = False) -> list[dict[str, Any]]:
        select_payload = ", before_json, after_json" if include_payload else ""
        return fetch_all(
            f"""
            SELECT
                audit_id,
                actor_role,
                actor_name,
                action,
                entity,
                entity_key,
                created_at
                {select_payload}
            FROM audit_log
            ORDER BY created_at DESC, audit_id DESC
            LIMIT %s
            """,
            (limit,),
        )

    def create(
        self,
        *,
        actor_role: str,
        actor_name: str,
        action: str,
        entity: str,
        entity_key: str,
        before_json: dict[str, Any] | None,
        after_json: dict[str, Any] | None,
    ) -> None:
        execute(
            """
            INSERT INTO audit_log (
                actor_role, actor_name, action, entity, entity_key, before_json, after_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                actor_role,
                actor_name,
                action,
                entity,
                entity_key,
                Jsonb(_json_compatible(before_json)) if before_json is not None else None,
                Jsonb(_json_compatible(after_json)) if after_json is not None else None,
            ),
        )
