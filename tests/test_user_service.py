import unittest
from unittest.mock import Mock, patch

from app.core.exceptions import UserFacingError
from app.services.user_service import UserService


class UserServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = UserService()
        self.service.repository = Mock()
        self.approver = {
            "user_id": 1,
            "username": "root",
            "full_name": "Root Admin",
            "role": "super_admin",
        }

    def test_approve_user_updates_pending_user(self) -> None:
        self.service.repository.get_by_id.return_value = {
            "user_id": 7,
            "username": "amina",
            "full_name": "Amina Safi",
            "role": "viewer",
            "is_active": False,
            "email": "amina@example.com",
        }
        self.service.repository.approve_pending.return_value = {
            "user_id": 7,
            "username": "amina",
            "full_name": "Amina Safi",
            "role": "manager",
            "is_active": True,
            "email": "amina@example.com",
        }

        with patch("app.services.user_service.log_audit_event") as log_audit_event:
            updated = self.service.approve_user(7, self.approver, "manager", True)

        self.assertEqual(updated["role"], "manager")
        self.service.repository.approve_pending.assert_called_once_with(7, 1, True, "manager")
        log_audit_event.assert_called_once()

    def test_approve_user_rejects_already_active_user(self) -> None:
        self.service.repository.get_by_id.return_value = {
            "user_id": 7,
            "username": "amina",
            "full_name": "Amina Safi",
            "role": "viewer",
            "is_active": True,
            "email": "amina@example.com",
        }

        with self.assertRaises(UserFacingError):
            self.service.approve_user(7, self.approver, "manager", True)

        self.service.repository.approve_pending.assert_not_called()

    def test_approve_user_rejects_invalid_role(self) -> None:
        self.service.repository.get_by_id.return_value = {
            "user_id": 7,
            "username": "amina",
            "full_name": "Amina Safi",
            "role": "viewer",
            "is_active": False,
            "email": "amina@example.com",
        }

        with self.assertRaises(UserFacingError):
            self.service.approve_user(7, self.approver, "super_admin", True)

        self.service.repository.approve_pending.assert_not_called()

    def test_approve_user_handles_stale_pending_update(self) -> None:
        self.service.repository.get_by_id.return_value = {
            "user_id": 7,
            "username": "amina",
            "full_name": "Amina Safi",
            "role": "viewer",
            "is_active": False,
            "email": "amina@example.com",
        }
        self.service.repository.approve_pending.return_value = None

        with self.assertRaises(UserFacingError):
            self.service.approve_user(7, self.approver, "manager", True)


if __name__ == "__main__":
    unittest.main()
