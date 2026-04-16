from datetime import date, datetime
from decimal import Decimal
import unittest

from app.repositories.audit_repository import _json_compatible


class AuditRepositoryTests(unittest.TestCase):
    def test_json_compatible_converts_database_values(self) -> None:
        converted = _json_compatible(
            {
                "start_date": date(2026, 4, 13),
                "created_at": datetime(2026, 4, 13, 10, 30),
                "amount": Decimal("12.50"),
                "file": b"abc",
            }
        )

        self.assertEqual(converted["start_date"], "2026-04-13")
        self.assertEqual(converted["created_at"], "2026-04-13T10:30:00")
        self.assertEqual(converted["amount"], "12.50")
        self.assertEqual(converted["file"], {"type": "binary", "size": 3})


if __name__ == "__main__":
    unittest.main()
