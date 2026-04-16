import unittest

import pandas as pd

from app.design.components.tables import (
    _format_boolean_text,
    _format_datetime_text,
    _format_status_text,
    _status_cell_style,
    _style_table,
)


class TableFormattingTests(unittest.TestCase):
    def test_status_text_is_humanized(self) -> None:
        self.assertEqual(_format_status_text("IN_PROGRESS"), "In Progress")

    def test_boolean_labels_follow_column_meaning(self) -> None:
        self.assertEqual(_format_boolean_text("has_cv_file", True), "Ready")
        self.assertEqual(_format_boolean_text("is_active", False), "Inactive")
        self.assertEqual(_format_boolean_text("is_current_active", True), "Current")

    def test_datetime_values_are_formatted_cleanly(self) -> None:
        self.assertEqual(_format_datetime_text(pd.Timestamp("2026-04-14 13:45:00")), "2026-04-14 13:45")

    def test_status_style_returns_colored_badge_css(self) -> None:
        css = _status_cell_style("Active")
        self.assertIn("background-color", css)
        self.assertIn("font-weight: 700", css)

    def test_style_table_formats_status_dates_and_links(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "status": "ACTIVE",
                    "start_date": pd.Timestamp("2026-04-14"),
                    "project_document_link": "https://example.com/doc",
                    "is_active": True,
                }
            ]
        )

        table_data, column_config = _style_table(frame)

        self.assertTrue(hasattr(table_data, "data"))
        formatted = table_data.data.iloc[0]
        self.assertEqual(formatted["status"], "Active")
        self.assertEqual(formatted["start_date"], "2026-04-14 00:00")
        self.assertEqual(formatted["is_active"], "Active")
        self.assertIn("project_document_link", column_config)


if __name__ == "__main__":
    unittest.main()
