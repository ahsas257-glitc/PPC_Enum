import unittest
from unittest.mock import Mock, patch

from app.core.security import hash_password
from app.core.session import get_current_user, login_user, logout_user
from app.services.auth_service import AuthService


class AuthServiceTests(unittest.TestCase):
    def test_login_accepts_email_and_returns_safe_user(self) -> None:
        auth_service = AuthService()
        auth_service.user_repository = Mock()
        auth_service.user_repository.get_auth_by_identifier.return_value = {
            "user_id": 7,
            "username": "amina",
            "full_name": "Amina Safi",
            "role": "admin",
            "is_active": True,
            "email": "amina@example.com",
            "password_hash": hash_password("top-secret"),
        }
        auth_service.user_repository.get_by_id.return_value = {
            "user_id": 7,
            "username": "amina",
            "full_name": "Amina Safi",
            "role": "admin",
            "is_active": True,
            "email": "amina@example.com",
        }

        user = auth_service.login("amina@example.com", "top-secret")

        self.assertEqual(user["email"], "amina@example.com")
        self.assertNotIn("password_hash", user)
        auth_service.user_repository.get_auth_by_identifier.assert_called_once_with("amina@example.com")
        auth_service.user_repository.get_by_id.assert_called_once_with(7)

    def test_login_returns_none_for_invalid_password(self) -> None:
        auth_service = AuthService()
        auth_service.user_repository = Mock()
        auth_service.user_repository.get_auth_by_identifier.return_value = {
            "user_id": 7,
            "username": "amina",
            "full_name": "Amina Safi",
            "role": "admin",
            "is_active": True,
            "email": "amina@example.com",
            "password_hash": hash_password("correct-password"),
        }

        user = auth_service.login("amina@example.com", "wrong-password")

        self.assertIsNone(user)
        auth_service.user_repository.get_by_id.assert_not_called()


class SessionTests(unittest.TestCase):
    @patch("app.core.session.st")
    def test_login_user_stores_only_safe_fields(self, streamlit_mock) -> None:
        streamlit_mock.session_state = {}

        login_user(
            {
                "user_id": 3,
                "username": "admin",
                "full_name": "System Admin",
                "role": "super_admin",
                "is_active": True,
                "email": "admin@example.com",
                "password_hash": "hidden",
                "approved_at": "2026-04-14T08:00:00",
            }
        )

        self.assertEqual(
            get_current_user(),
            {
                "user_id": 3,
                "username": "admin",
                "full_name": "System Admin",
                "role": "super_admin",
                "email": "admin@example.com",
                "is_active": True,
            },
        )
        self.assertNotIn("password_hash", streamlit_mock.session_state["current_user"])
        self.assertIsNone(streamlit_mock.session_state["active_page"])
        self.assertIsNone(streamlit_mock.session_state["sidebar_active_page"])

        logout_user()
        self.assertIsNone(streamlit_mock.session_state["current_user"])
        self.assertIsNone(streamlit_mock.session_state["active_page"])
        self.assertIsNone(streamlit_mock.session_state["sidebar_active_page"])


if __name__ == "__main__":
    unittest.main()
