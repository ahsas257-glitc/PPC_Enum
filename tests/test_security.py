import unittest

from app.core.security import hash_password, verify_password


class SecurityTests(unittest.TestCase):
    def test_password_round_trip(self) -> None:
        encoded = hash_password("s3cret-pass")
        self.assertTrue(verify_password("s3cret-pass", encoded))
        self.assertFalse(verify_password("wrong", encoded))


if __name__ == "__main__":
    unittest.main()
