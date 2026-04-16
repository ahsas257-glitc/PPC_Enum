import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.pages.admin.search_reports_page import (
    _build_project_assignment_report,
    _normalize_digits,
    _payment_type_label,
    _report_file_name,
)


class SearchReportsPageTests(unittest.TestCase):
    def test_normalize_digits_strips_non_numeric_characters(self) -> None:
        self.assertEqual(_normalize_digits("+93 (700) 123-456"), "93700123456")

    def test_payment_type_label_humanizes_known_values(self) -> None:
        self.assertEqual(_payment_type_label("BANK_ACCOUNT"), "Bank account")
        self.assertEqual(_payment_type_label("MOBILE_CREDIT"), "Mobile money")

    def test_report_file_name_uses_surveyor_code_slug(self) -> None:
        profile = {"surveyor_code": "PPC-KBL-001"}
        self.assertEqual(_report_file_name("HR Letter", profile), "hr_letter_ppc_kbl_001.html")

    def test_project_assignment_report_marks_current_projects(self) -> None:
        profile = {"surveyor_code": "PPC-KBL-001", "surveyor_name": "Amina Safi"}
        html = _build_project_assignment_report(
            profile,
            [
                {
                    "project_code": "ACME-PDM-P01",
                    "project_name": "Post Distribution Monitoring",
                    "project_status": "ACTIVE",
                    "assignment_status": "ACTIVE",
                    "role": "Surveyor",
                    "work_province_name": "Kabul",
                    "assignment_start_date": "2026-04-01",
                    "assignment_end_date": None,
                    "client_name": "ACME",
                    "is_current_active": True,
                }
            ],
        )

        self.assertIn("Project Work History", html)
        self.assertIn("Post Distribution Monitoring", html)
        self.assertIn("Current", html)
        self.assertIn("Internal Official Record", html)
        self.assertIn("Control number", html)
        self.assertIn("Prepared by", html)
        self.assertIn("Current assignment rule", html)

    @patch("app.pages.admin.search_reports_page.ProjectService")
    @patch("app.pages.admin.search_reports_page.BankAccountService")
    @patch("app.pages.admin.search_reports_page.SurveyorService")
    def test_search_reports_page_renders_with_mocked_data(self, mock_surveyor_service, mock_bank_service, mock_project_service) -> None:
        surveyor_service = mock_surveyor_service.return_value
        surveyor_service.search_profiles.return_value = [
            {
                "surveyor_id": 1,
                "surveyor_code": "PPC-KBL-001",
                "surveyor_name": "Amina Safi",
                "current_province_name": "Kabul",
                "phone_number": "0700123456",
                "tazkira_no": "12345",
                "document_count": 4,
                "account_count": 1,
            }
        ]
        surveyor_service.get_profile_detail.return_value = {
            "surveyor_id": 1,
            "surveyor_code": "PPC-KBL-001",
            "surveyor_name": "Amina Safi",
            "gender": "Female",
            "father_name": "Karim Safi",
            "tazkira_no": "12345",
            "email_address": "amina@example.com",
            "whatsapp_number": "0700123456",
            "phone_number": "0700123456",
            "permanent_province_name": "Kabul",
            "current_province_name": "Kabul",
            "document_count": 4,
            "account_count": 1,
            "active_account_count": 1,
            "default_bank_name": "Azizi Bank",
            "default_payment_type": "BANK_ACCOUNT",
            "default_payout_value": "99887766",
            "bank_names": "Azizi Bank",
            "has_cv_file": True,
            "has_tazkira_image": True,
            "has_tazkira_pdf": True,
            "has_tazkira_word": True,
            "cv_file_name": "cv.pdf",
            "tazkira_image_name": "tazkira.jpg",
            "tazkira_pdf_name": "tazkira.pdf",
            "tazkira_word_name": "tazkira.docx",
        }

        bank_service = mock_bank_service.return_value
        bank_service.list_surveyor_accounts.return_value = [
            {
                "bank_name": "Azizi Bank",
                "payment_type": "BANK_ACCOUNT",
                "account_title": "Amina Safi",
                "account_number": "99887766",
                "mobile_number": None,
                "is_default": True,
                "is_active": True,
            }
        ]
        project_service = mock_project_service.return_value
        project_service.list_assignments_for_surveyor.return_value = [
            {
                "project_code": "ACME-PDM-P01",
                "project_name": "Post Distribution Monitoring",
                "project_status": "ACTIVE",
                "assignment_status": "ACTIVE",
                "is_current_active": True,
            }
        ]

        app = AppTest.from_file("streamlit_app.py")
        app.session_state["current_user"] = {
            "user_id": 1,
            "username": "admin@example.com",
            "full_name": "System Admin",
            "role": "super_admin",
            "is_active": True,
            "email": "admin@example.com",
        }
        app.session_state["active_page"] = "Search & Reports"
        app.session_state["search_reports_query"] = "Amina"
        app.run(timeout=90)

        self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
