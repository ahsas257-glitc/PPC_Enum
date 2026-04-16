import unittest

from app.core.permissions import pages_for_role


class PermissionRegistryTests(unittest.TestCase):
    def test_search_reports_is_first_for_admin_roles(self) -> None:
        super_admin_labels = [page["label"] for page in pages_for_role("super_admin")]
        admin_labels = [page["label"] for page in pages_for_role("admin")]
        manager_labels = [page["label"] for page in pages_for_role("manager")]
        self.assertEqual(super_admin_labels[0], "Search & Reports")
        self.assertEqual(admin_labels[0], "Search & Reports")
        self.assertEqual(manager_labels[0], "Search & Reports")

    def test_search_reports_is_available_to_admin_roles(self) -> None:
        admin_labels = [page["label"] for page in pages_for_role("admin")]
        manager_labels = [page["label"] for page in pages_for_role("manager")]
        self.assertIn("Search & Reports", admin_labels)
        self.assertIn("Search & Reports", manager_labels)

    def test_search_reports_is_not_available_to_viewers(self) -> None:
        viewer_labels = [page["label"] for page in pages_for_role("viewer")]
        self.assertNotIn("Search & Reports", viewer_labels)


if __name__ == "__main__":
    unittest.main()
