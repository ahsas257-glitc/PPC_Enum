from typing import Any

from app.core.database import execute, fetch_all, fetch_one


class UserRepository:
    _SAFE_COLUMNS = """
        user_id,
        username,
        full_name,
        role,
        is_active,
        email,
        approved_by,
        approved_at,
        created_at
    """
    _AUTH_COLUMNS = f"{_SAFE_COLUMNS}, password_hash"

    def list_all(self) -> list[dict[str, Any]]:
        return fetch_all(
            """
            SELECT
                u.user_id,
                u.username,
                u.full_name,
                u.role,
                u.is_active,
                u.email,
                u.approved_by,
                u.approved_at,
                u.created_at,
                approver.full_name AS approved_by_name
            FROM users u
            LEFT JOIN users approver ON approver.user_id = u.approved_by
            ORDER BY u.user_id
            """
        )

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        return fetch_one(f"SELECT {self._SAFE_COLUMNS} FROM users WHERE username = %s", (username,))

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        return fetch_one(f"SELECT {self._SAFE_COLUMNS} FROM users WHERE email = %s", (email,))

    def get_auth_by_identifier(self, identifier: str) -> dict[str, Any] | None:
        clean_identifier = identifier.strip()
        return fetch_one(
            f"""
            SELECT {self._AUTH_COLUMNS}
            FROM users
            WHERE LOWER(username) = LOWER(%s)
               OR LOWER(email) = LOWER(%s)
            ORDER BY user_id
            LIMIT 1
            """,
            (clean_identifier, clean_identifier),
        )

    def get_by_id(self, user_id: int) -> dict[str, Any] | None:
        return fetch_one(f"SELECT {self._SAFE_COLUMNS} FROM users WHERE user_id = %s", (user_id,))

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        return execute(
            """
            INSERT INTO users (username, password_hash, full_name, role, is_active, email)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING user_id, username, full_name, role, is_active, email, approved_by, approved_at, created_at
            """,
            (
                payload["username"],
                payload["password_hash"],
                payload["full_name"],
                payload["role"],
                payload["is_active"],
                payload["email"],
            ),
            returning=True,
        )

    def approve_pending(self, user_id: int, approver_id: int, is_active: bool, role: str) -> dict[str, Any] | None:
        return execute(
            """
            UPDATE users
            SET is_active = %s, role = %s, approved_by = %s, approved_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
              AND is_active = FALSE
            RETURNING user_id, username, full_name, role, is_active, email, approved_by, approved_at, created_at
            """,
            (is_active, role, approver_id, user_id),
            returning=True,
        )

    def update_profile(self, user_id: int, full_name: str, email: str) -> dict[str, Any]:
        return execute(
            """
            UPDATE users
            SET full_name = %s, email = %s
            WHERE user_id = %s
            RETURNING user_id, username, full_name, role, is_active, email, approved_by, approved_at, created_at
            """,
            (full_name, email, user_id),
            returning=True,
        )
