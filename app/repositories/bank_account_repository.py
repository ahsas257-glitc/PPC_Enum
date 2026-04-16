from app.core.database import execute, fetch_all, transaction


class BankAccountRepository:
    def list_all(self, limit: int = 500) -> list[dict]:
        return fetch_all(
            """
            SELECT sba.*,
                   s.surveyor_name,
                   s.surveyor_code,
                   b.bank_name
            FROM surveyor_bank_accounts sba
            JOIN surveyors s ON s.surveyor_id = sba.surveyor_id
            JOIN banks b ON b.bank_id = sba.bank_id
            ORDER BY sba.bank_account_id DESC
            LIMIT %s
            """,
            (limit,),
        )

    def list_for_surveyor(self, surveyor_id: int) -> list[dict]:
        return fetch_all(
            """
            SELECT sba.*,
                   b.bank_name
            FROM surveyor_bank_accounts sba
            JOIN banks b ON b.bank_id = sba.bank_id
            WHERE sba.surveyor_id = %s
            ORDER BY sba.is_default DESC, sba.is_active DESC, sba.bank_account_id DESC
            """,
            (surveyor_id,),
        )

    def create(self, payload: dict) -> dict:
        with transaction() as conn:
            if payload["is_default"]:
                execute(
                    "UPDATE surveyor_bank_accounts SET is_default = false WHERE surveyor_id = %s",
                    (payload["surveyor_id"],),
                    connection=conn,
                )
            return execute(
                """
                INSERT INTO surveyor_bank_accounts (
                    surveyor_id, bank_id, payment_type, account_number, mobile_number,
                    account_title, is_default, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    payload["surveyor_id"],
                    payload["bank_id"],
                    payload["payment_type"],
                    payload["account_number"],
                    payload["mobile_number"],
                    payload["account_title"],
                    payload["is_default"],
                    payload["is_active"],
                ),
                connection=conn,
                returning=True,
            )
