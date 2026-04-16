import unittest

from app.design.components.validation import (
    FORM_MESSAGE_KEY,
    email_errors,
    field_errors_from_message,
    phone_errors,
    required_errors,
    tazkira_errors,
)


class ValidationHelperTests(unittest.TestCase):
    def test_required_errors_returns_messages_for_blank_values(self) -> None:
        errors = required_errors(
            {
                "name": ("", "Enter the name."),
                "email": ("person@example.com", "Enter the email."),
                "items": ([], "Choose at least one item."),
            }
        )

        self.assertEqual(errors["name"], "Enter the name.")
        self.assertEqual(errors["items"], "Choose at least one item.")
        self.assertNotIn("email", errors)

    def test_format_helpers_ignore_blank_values(self) -> None:
        self.assertEqual(email_errors({"email": ("", "Enter a valid email.")}), {})
        self.assertEqual(phone_errors({"phone": ("", "Enter a valid phone.")}), {})

    def test_format_helpers_flag_invalid_values(self) -> None:
        self.assertIn("email", email_errors({"email": ("bad-email", "Enter a valid email.")}))
        self.assertIn("phone", phone_errors({"phone": ("123", "Enter a valid phone.")}))
        self.assertIn("phone", phone_errors({"phone": ("0700123456", "Enter a valid phone.")}))
        self.assertIn("tazkira", tazkira_errors({"tazkira": ("12345", "Enter a valid tazkira.")}))

    def test_format_helpers_accept_database_compatible_values(self) -> None:
        self.assertEqual(phone_errors({"phone": ("+93700123456", "Enter a valid phone.")}), {})
        self.assertEqual(tazkira_errors({"tazkira": ("1234-5678-90123", "Enter a valid tazkira.")}), {})

    def test_field_errors_from_message_maps_keywords(self) -> None:
        errors = field_errors_from_message(
            "This email is already used.",
            {"email_field": ("email",), "phone_field": ("phone",)},
        )

        self.assertEqual(errors[FORM_MESSAGE_KEY], "This email is already used.")
        self.assertEqual(errors["email_field"], "This email is already used.")
        self.assertNotIn("phone_field", errors)


if __name__ == "__main__":
    unittest.main()
