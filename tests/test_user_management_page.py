import unittest

from app.pages.owner.user_management_page import _default_approved_role, _pending_option_label


class UserManagementPageHelpersTests(unittest.TestCase):
    def test_default_approved_role_uses_requested_role_when_allowed(self) -> None:
        self.assertEqual(_default_approved_role({"role": "manager"}), "manager")

    def test_default_approved_role_falls_back_for_non_approvable_role(self) -> None:
        self.assertEqual(_default_approved_role({"role": "super_admin"}), "viewer")

    def test_pending_option_label_includes_name_email_and_role(self) -> None:
        label = _pending_option_label(
            {
                "full_name": "Amina Safi",
                "username": "amina",
                "email": "amina@example.com",
                "role": "manager",
            }
        )

        self.assertIn("Amina Safi", label)
        self.assertIn("amina@example.com", label)
        self.assertIn("requested: Manager", label)


if __name__ == "__main__":
    unittest.main()
