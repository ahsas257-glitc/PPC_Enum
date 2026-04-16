from app.core.security import hash_password, verify_password
from app.core.exceptions import UserFacingError, friendly_message_for_db_error
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self) -> None:
        self.user_repository = UserRepository()

    def login(self, username: str, password: str) -> dict | None:
        user = self.user_repository.get_auth_by_identifier(username)
        if not user:
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        return self.user_repository.get_by_id(user["user_id"])

    def register(self, full_name: str, username: str, email: str, password: str, role: str) -> dict:
        clean_username = username.strip()
        clean_email = email.strip()

        if self.user_repository.get_by_username(clean_username):
            raise UserFacingError("This username is already registered. Please use a different username.")
        if clean_email and self.user_repository.get_by_email(clean_email):
            raise UserFacingError("This email is already registered. Please use a different email.")

        try:
            return self.user_repository.create(
                {
                    "username": clean_username,
                    "password_hash": hash_password(password),
                    "full_name": full_name.strip(),
                    "role": role,
                    "is_active": False,
                    "email": clean_email,
                }
            )
        except Exception as exc:
            message = friendly_message_for_db_error(exc)
            if message:
                raise UserFacingError(message) from exc
            raise UserFacingError("Could not create the account right now. Please try again.") from exc
