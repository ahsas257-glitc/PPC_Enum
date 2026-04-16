import unittest

from streamlit.testing.v1 import AppTest


class AppSmokeTests(unittest.TestCase):
    def test_public_app_renders_without_exception(self) -> None:
        app = AppTest.from_file("streamlit_app.py")
        app.run(timeout=60)
        self.assertEqual(len(app.exception), 0)

    def test_super_admin_pages_render_without_exception(self) -> None:
        user = {
            "user_id": 1,
            "username": "admin@shabeer.com",
            "full_name": "System Admin",
            "role": "super_admin",
            "is_active": True,
            "email": "admin@shabeer.com",
        }
        pages = [
            "Search & Reports",
            "Dashboard",
            "Projects",
            "Surveyors",
            "Banks",
            "Bank Accounts",
            "Users",
            "Audit Logs",
            "Profile",
        ]
        for page in pages:
            with self.subTest(page=page):
                app = AppTest.from_file("streamlit_app.py")
                app.session_state["current_user"] = user
                app.session_state["active_page"] = page
                app.run(timeout=90)
                self.assertEqual(len(app.exception), 0)

    def test_dashboard_does_not_render_raw_html_markup(self) -> None:
        user = {
            "user_id": 1,
            "username": "admin@shabeer.com",
            "full_name": "System Admin",
            "role": "super_admin",
            "is_active": True,
            "email": "admin@shabeer.com",
        }
        app = AppTest.from_file("streamlit_app.py")
        app.session_state["current_user"] = user
        app.session_state["active_page"] = "Dashboard"
        app.run(timeout=90)

        markdown_values = [item.value for item in app.markdown]
        self.assertEqual(len(markdown_values), 1)
        self.assertTrue(markdown_values[0].startswith("<style>"))
        self.assertFalse(any("<div class=" in value for value in markdown_values))
        self.assertFalse(any("</div>" in value for value in markdown_values))

    def test_logout_does_not_raise_active_page_widget_error(self) -> None:
        user = {
            "user_id": 1,
            "username": "admin@shabeer.com",
            "full_name": "System Admin",
            "role": "super_admin",
            "is_active": True,
            "email": "admin@shabeer.com",
        }
        app = AppTest.from_file("streamlit_app.py")
        app.session_state["current_user"] = user
        app.session_state["active_page"] = "Dashboard"
        app.run(timeout=90)

        app.button[0].click().run(timeout=90)

        self.assertEqual(len(app.exception), 0)
        self.assertIsNone(app.session_state["current_user"])
        self.assertIsNone(app.session_state["active_page"])


if __name__ == "__main__":
    unittest.main()
