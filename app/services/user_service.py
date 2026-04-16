from app.core.audit import log_audit_event
from app.core.constants import APPROVABLE_USER_ROLES
from app.core.exceptions import UserFacingError, friendly_message_for_db_error
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self) -> None:
        self.repository = UserRepository()

    def list_users(self) -> list[dict]:
        return self.repository.list_all()

    def approve_user(self, user_id: int, approver: dict, role: str, is_active: bool = True) -> dict:
        before = self.repository.get_by_id(user_id)
        if not before:
            raise UserFacingError("The selected user no longer exists. Refresh the page and try again.")
        if before["is_active"]:
            raise UserFacingError("This user is already approved. Refresh the list and choose another user.")
        if role not in APPROVABLE_USER_ROLES:
            raise UserFacingError("Select a valid role for the approved user.")

        updated = self.repository.approve_pending(user_id, approver["user_id"], is_active, role)
        if not updated:
            raise UserFacingError("This user was already updated. Refresh the list and try again.")

        log_audit_event(
            actor_role=approver["role"],
            actor_name=approver["full_name"] or approver["username"],
            action="APPROVE_USER",
            entity="users",
            entity_key=str(user_id),
            before_json=before,
            after_json=updated,
        )
        return updated

    def update_profile(self, user: dict, full_name: str, email: str) -> dict:
        try:
            updated = self.repository.update_profile(user["user_id"], full_name, email)
        except Exception as exc:
            message = friendly_message_for_db_error(exc)
            if message:
                raise UserFacingError(message) from exc
            raise UserFacingError("Could not update profile right now. Please try again.") from exc
        log_audit_event(
            actor_role=user["role"],
            actor_name=user["full_name"] or user["username"],
            action="UPDATE_PROFILE",
            entity="users",
            entity_key=str(user["user_id"]),
            before_json={"full_name": user["full_name"], "email": user["email"]},
            after_json={"full_name": full_name, "email": email},
        )
        return updated
