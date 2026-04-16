from contextlib import contextmanager
import unittest
from unittest.mock import MagicMock, patch

from app.core.exceptions import UserFacingError
from app.pages.admin.search_reports_page import _cache_get_or_set, SESSION_CACHE_TTL_SECONDS
from app.pages.admin.surveyors_page import MAX_UPLOAD_SIZE_BYTES, _file_payload
from app.repositories.bank_account_repository import BankAccountRepository
from app.repositories.project_repository import ProjectRepository
from app.services.project_service import ProjectService
from app.pages.admin.projects_page import (
    _build_pdf_report_bytes,
    _build_word_report_bytes,
    _dataframe_to_csv_bytes,
    _frames_to_xlsx_bytes,
)
import pandas as pd


class RepositoryTransactionTests(unittest.TestCase):
    @patch("app.repositories.bank_account_repository.execute")
    @patch("app.repositories.bank_account_repository.transaction")
    def test_bank_account_create_runs_in_single_transaction(self, transaction_mock, execute_mock) -> None:
        connection = object()

        @contextmanager
        def fake_transaction():
            yield connection

        transaction_mock.side_effect = fake_transaction
        execute_mock.side_effect = [None, {"bank_account_id": 55}]

        created = BankAccountRepository().create(
            {
                "surveyor_id": 1,
                "bank_id": 2,
                "payment_type": "BANK_ACCOUNT",
                "account_number": "123",
                "mobile_number": None,
                "account_title": "Amina",
                "is_default": True,
                "is_active": True,
            }
        )

        self.assertEqual(created["bank_account_id"], 55)
        self.assertEqual(execute_mock.call_args_list[0].kwargs["connection"], connection)
        self.assertEqual(execute_mock.call_args_list[1].kwargs["connection"], connection)

    @patch("app.repositories.project_repository.execute")
    @patch("app.repositories.project_repository.transaction")
    def test_assignment_create_keeps_parent_and_extra_provinces_in_one_transaction(self, transaction_mock, execute_mock) -> None:
        connection = object()

        @contextmanager
        def fake_transaction():
            yield connection

        transaction_mock.side_effect = fake_transaction
        execute_mock.side_effect = [
            {"project_surveyor_id": 77},
            None,
            None,
        ]

        created = ProjectRepository().create_assignment(
            {
                "project_id": 10,
                "surveyor_id": 5,
                "role": "Surveyor",
                "work_province_code": "KBL",
                "start_date": "2026-04-01",
                "end_date": None,
                "status": "ACTIVE",
                "notes": None,
                "extra_province_codes": ["BAL", "HER"],
            }
        )

        self.assertEqual(created["project_surveyor_id"], 77)
        self.assertEqual(execute_mock.call_args_list[0].kwargs["connection"], connection)
        self.assertEqual(execute_mock.call_args_list[1].kwargs["connection"], connection)
        self.assertEqual(execute_mock.call_args_list[2].kwargs["connection"], connection)


class ProjectServiceTests(unittest.TestCase):
    @patch("app.services.project_service.log_audit_event")
    @patch("app.services.project_service.transaction")
    def test_create_project_reserves_sequence_and_creates_with_one_connection(self, transaction_mock, audit_mock) -> None:
        connection = object()

        @contextmanager
        def fake_transaction():
            yield connection

        transaction_mock.side_effect = fake_transaction
        service = ProjectService()
        service.repository = MagicMock()
        service.repository.reserve_next_phase_sequence.return_value = 3
        service.repository.create.return_value = {"project_id": 41, "project_code": "ACME-PDM-P03"}

        created = service.create_project(
            {"role": "admin", "full_name": "Ops Admin", "username": "ops"},
            {
                "project_name": "Post Distribution Monitoring",
                "project_short_name": "PDM",
                "client_name": "ACME",
                "implementing_partner": None,
                "project_type": "Field",
                "start_date": __import__("datetime").date(2026, 4, 1),
                "end_date": None,
                "status": "ACTIVE",
                "notes": None,
                "project_document_link": None,
            },
        )

        self.assertEqual(created["project_id"], 41)
        service.repository.reserve_next_phase_sequence.assert_called_once_with("ACME", "PDM", 2026, connection=connection)
        self.assertEqual(service.repository.create.call_args.kwargs["connection"], connection)
        audit_mock.assert_called_once()

    @patch("app.services.project_service.log_audit_event")
    def test_create_assignments_logs_each_saved_assignment(self, audit_mock) -> None:
        service = ProjectService()
        service.repository = MagicMock()
        service.repository.create_assignments.return_value = [
            {"project_surveyor_id": 90},
            {"project_surveyor_id": 91},
        ]

        created = service.create_assignments(
            {"role": "admin", "full_name": "Ops Admin", "username": "ops"},
            [
                {"project_id": 1, "surveyor_id": 2},
                {"project_id": 1, "surveyor_id": 3},
            ],
        )

        self.assertEqual(len(created), 2)
        service.repository.create_assignments.assert_called_once()
        self.assertEqual(audit_mock.call_count, 2)

    def test_list_assignment_conflicts_forwards_to_repository(self) -> None:
        service = ProjectService()
        service.repository = MagicMock()
        service.repository.list_assignment_conflicts.return_value = [{"project_surveyor_id": 11}]

        conflicts = service.list_assignment_conflicts(
            project_id=4,
            surveyor_ids=[8, 9],
            start_date="2026-04-10",
            end_date="2026-04-28",
        )

        self.assertEqual(conflicts, [{"project_surveyor_id": 11}])
        service.repository.list_assignment_conflicts.assert_called_once()


class UploadAndCacheTests(unittest.TestCase):
    def test_file_payload_rejects_oversized_uploads(self) -> None:
        file_obj = MagicMock()
        file_obj.size = MAX_UPLOAD_SIZE_BYTES + 1

        with self.assertRaises(UserFacingError):
            _file_payload(file_obj, "CV file")

    @patch("app.pages.admin.search_reports_page.time.time")
    @patch("app.pages.admin.search_reports_page.st")
    def test_search_reports_session_cache_expires(self, streamlit_mock, time_mock) -> None:
        streamlit_mock.session_state = {}
        resolver = MagicMock(side_effect=[{"value": 1}, {"value": 2}])

        time_mock.return_value = 1000.0
        first = _cache_get_or_set("sample_cache", "item", resolver)
        second = _cache_get_or_set("sample_cache", "item", resolver)

        time_mock.return_value = 1000.0 + SESSION_CACHE_TTL_SECONDS + 1
        third = _cache_get_or_set("sample_cache", "item", resolver)

        self.assertEqual(first, {"value": 1})
        self.assertEqual(second, {"value": 1})
        self.assertEqual(third, {"value": 2})
        self.assertEqual(resolver.call_count, 2)


class ProjectExportTests(unittest.TestCase):
    def test_project_export_builders_return_expected_file_signatures(self) -> None:
        frame = pd.DataFrame(
            [
                {"project_code": "P-001", "project_name": "Baseline", "status": "ACTIVE"},
                {"project_code": "P-002", "project_name": "Follow Up", "status": "PLANNED"},
            ]
        )

        csv_bytes = _dataframe_to_csv_bytes(frame)
        xlsx_bytes = _frames_to_xlsx_bytes({"Projects": frame})
        word_bytes = _build_word_report_bytes("Projects", "Statuses: All", [("Total", "2")], [("Project Directory", frame)])
        pdf_bytes = _build_pdf_report_bytes("Projects", "Statuses: All", [("Total", "2")], [("Project Directory", frame)])

        self.assertIn("Project Code".encode("utf-8"), csv_bytes)
        self.assertTrue(xlsx_bytes.startswith(b"PK"))
        self.assertTrue(word_bytes.startswith(b"PK"))
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
