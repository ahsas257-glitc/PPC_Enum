import unittest
from unittest.mock import patch

from app.repositories.project_repository import ProjectRepository
from app.services.project_service import _slug


class ProjectServiceTests(unittest.TestCase):
    def test_slug_uses_initials_for_multi_word_values(self) -> None:
        self.assertEqual(_slug("Post Distribution Monitoring", "X"), "PDM")

    def test_slug_falls_back_when_value_is_empty(self) -> None:
        self.assertEqual(_slug("", "GEN"), "GEN")

    @patch("app.repositories.project_repository.fetch_one")
    def test_phase_sequence_lookup_matches_database_unique_key(self, fetch_one_mock) -> None:
        ProjectRepository().get_phase_sequence("CLIENT", "PROJECT", 2026)

        query, params = fetch_one_mock.call_args.args
        self.assertEqual(params, ("CLIENT", "PROJECT", 2026))
        self.assertIn("start_year IS NOT DISTINCT FROM %s", query)


if __name__ == "__main__":
    unittest.main()
