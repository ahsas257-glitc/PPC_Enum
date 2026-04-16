from app.core.database import execute, fetch_all, fetch_one


class BankRepository:
    def list_all(self) -> list[dict]:
        return fetch_all("SELECT * FROM banks ORDER BY bank_name")

    def get_by_id(self, bank_id: int) -> dict | None:
        return fetch_one("SELECT * FROM banks WHERE bank_id = %s", (bank_id,))

    def create(self, bank_name: str, payment_method: str, is_active: bool) -> dict:
        return execute(
            """
            INSERT INTO banks (bank_name, payment_method, is_active)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (bank_name, payment_method, is_active),
            returning=True,
        )
