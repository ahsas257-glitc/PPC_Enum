from app.core.database import execute, fetch_all, fetch_one


class SurveyorRepository:
    _PROFILE_SELECT = """
        SELECT
            s.surveyor_id,
            s.surveyor_code,
            s.surveyor_name,
            s.gender,
            s.father_name,
            s.tazkira_no,
            s.email_address,
            s.whatsapp_number,
            s.phone_number,
            s.permanent_province_code,
            s.current_province_code,
            s.cv_link,
            s.cv_file_name,
            s.tazkira_image_name,
            s.tazkira_pdf_name,
            s.tazkira_word_name,
            pp.province_name AS permanent_province_name,
            cp.province_name AS current_province_name,
            (s.cv_file IS NOT NULL) AS has_cv_file,
            (s.tazkira_image IS NOT NULL) AS has_tazkira_image,
            (s.tazkira_pdf IS NOT NULL) AS has_tazkira_pdf,
            (s.tazkira_word IS NOT NULL) AS has_tazkira_word,
            (
                (s.cv_file IS NOT NULL)::int +
                (s.tazkira_image IS NOT NULL)::int +
                (s.tazkira_pdf IS NOT NULL)::int +
                (s.tazkira_word IS NOT NULL)::int
            ) AS document_count,
            COALESCE(ar.account_count, 0) AS account_count,
            COALESCE(ar.active_account_count, 0) AS active_account_count,
            ar.default_bank_name,
            ar.default_payment_type,
            ar.default_payout_value,
            ar.bank_names
    """

    _PROFILE_FROM = """
        FROM surveyors s
        LEFT JOIN provinces pp ON pp.province_code = s.permanent_province_code
        LEFT JOIN provinces cp ON cp.province_code = s.current_province_code
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*)::int AS account_count,
                COUNT(*) FILTER (WHERE sba.is_active)::int AS active_account_count,
                MAX(CASE WHEN sba.is_default THEN b.bank_name END) AS default_bank_name,
                MAX(CASE WHEN sba.is_default THEN sba.payment_type END) AS default_payment_type,
                MAX(CASE WHEN sba.is_default THEN COALESCE(sba.account_number, sba.mobile_number) END) AS default_payout_value,
                STRING_AGG(DISTINCT b.bank_name, ', ' ORDER BY b.bank_name) AS bank_names
            FROM surveyor_bank_accounts sba
            JOIN banks b ON b.bank_id = sba.bank_id
            WHERE sba.surveyor_id = s.surveyor_id
        ) ar ON true
    """

    def list_all(self, limit: int = 500) -> list[dict]:
        return fetch_all(
            """
            SELECT
                   s.surveyor_id,
                   s.surveyor_code,
                   s.surveyor_name,
                   s.gender,
                   s.father_name,
                   s.tazkira_no,
                   s.email_address,
                   s.whatsapp_number,
                   s.phone_number,
                   s.permanent_province_code,
                   s.current_province_code,
                   s.cv_link,
                   s.cv_file_name,
                   s.tazkira_image_name,
                   s.tazkira_pdf_name,
                   s.tazkira_word_name,
                   pp.province_name AS permanent_province_name,
                   cp.province_name AS current_province_name,
                   (s.cv_file IS NOT NULL) AS has_cv_file,
                   (s.tazkira_image IS NOT NULL) AS has_tazkira_image,
                   (s.tazkira_pdf IS NOT NULL) AS has_tazkira_pdf,
                   (s.tazkira_word IS NOT NULL) AS has_tazkira_word
            FROM surveyors s
            LEFT JOIN provinces pp ON pp.province_code = s.permanent_province_code
            LEFT JOIN provinces cp ON cp.province_code = s.current_province_code
            ORDER BY s.surveyor_id DESC
            LIMIT %s
            """,
            (limit,),
        )

    def list_lookup(self, limit: int = 1000) -> list[dict]:
        return fetch_all(
            """
            SELECT surveyor_id, surveyor_code, surveyor_name
            FROM surveyors
            ORDER BY surveyor_name
            LIMIT %s
            """,
            (limit,),
        )

    def list_assignment_candidates(self, province_code: str | list[str] | tuple[str, ...] | None = None, limit: int = 1000) -> list[dict]:
        province_codes: list[str] = []
        if isinstance(province_code, str):
            province_codes = [province_code] if province_code else []
        elif province_code:
            province_codes = [code for code in province_code if code]
        return fetch_all(
            f"""
            SELECT
                   s.surveyor_id,
                   s.surveyor_code,
                   s.surveyor_name,
                   s.current_province_code,
                   s.permanent_province_code,
                   cp.province_name AS current_province_name,
                   pp.province_name AS permanent_province_name,
                   COALESCE(cp.province_code, pp.province_code) AS availability_province_code,
                   COALESCE(cp.province_name, pp.province_name) AS availability_province_name,
                   (
                       (s.cv_file IS NOT NULL)::int +
                       (s.tazkira_image IS NOT NULL)::int +
                       (s.tazkira_pdf IS NOT NULL)::int +
                       (s.tazkira_word IS NOT NULL)::int
                   ) AS document_count,
                   COALESCE(ar.account_count, 0) AS account_count,
                   COALESCE(ar.active_account_count, 0) AS active_account_count,
                   COALESCE(ap.active_project_count, 0) AS active_project_count
            FROM surveyors s
            LEFT JOIN provinces cp ON cp.province_code = s.current_province_code
            LEFT JOIN provinces pp ON pp.province_code = s.permanent_province_code
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*)::int AS account_count,
                    COUNT(*) FILTER (WHERE sba.is_active)::int AS active_account_count
                FROM surveyor_bank_accounts sba
                WHERE sba.surveyor_id = s.surveyor_id
            ) ar ON true
            LEFT JOIN LATERAL (
                SELECT COUNT(DISTINCT ps.project_id)::int AS active_project_count
                FROM project_surveyors ps
                JOIN projects p ON p.project_id = ps.project_id
                WHERE ps.surveyor_id = s.surveyor_id
                  AND ps.status = 'ACTIVE'
                  AND p.status = 'ACTIVE'
                  AND ps.start_date <= CURRENT_DATE
                  AND (ps.end_date IS NULL OR ps.end_date >= CURRENT_DATE)
            ) ap ON true
            WHERE (
                %s = 0
                OR COALESCE(s.current_province_code, s.permanent_province_code) = ANY(%s)
            )
            ORDER BY s.surveyor_name ASC, s.surveyor_id DESC
            LIMIT %s
            """,
            (len(province_codes), province_codes, limit),
        )

    def list_recent_profiles(self, limit: int = 6) -> list[dict]:
        return fetch_all(
            f"""
            {self._PROFILE_SELECT}
            {self._PROFILE_FROM}
            ORDER BY s.surveyor_id DESC
            LIMIT %s
            """,
            (limit,),
        )

    def search_profiles(self, query_text: str, search_by: str = "SMART", limit: int = 12) -> list[dict]:
        term = query_text.strip()
        if not term:
            return []

        normalized = term.lower()
        prefix = f"{term}%"
        contains = f"%{term}%"
        digits = "".join(character for character in term if character.isdigit())
        digit_contains = f"%{digits}%"

        if search_by == "ID":
            where_clause = "(CAST(s.surveyor_id AS TEXT) = %s OR s.surveyor_code ILIKE %s)"
            score_clause = """
                CASE
                    WHEN CAST(s.surveyor_id AS TEXT) = %s THEN 140
                    WHEN LOWER(s.surveyor_code) = %s THEN 130
                    WHEN s.surveyor_code ILIKE %s THEN 112
                    ELSE 80
                END
            """
            params = (term, normalized, prefix, term, prefix, limit)
        elif search_by == "NAME":
            where_clause = "s.surveyor_name ILIKE %s"
            score_clause = """
                CASE
                    WHEN LOWER(s.surveyor_name) = %s THEN 130
                    WHEN s.surveyor_name ILIKE %s THEN 112
                    ELSE 88
                END
            """
            params = (normalized, prefix, contains, limit)
        elif search_by == "NUMBER":
            if not digits:
                return []
            where_clause = """
                (
                    regexp_replace(COALESCE(s.phone_number, ''), '[^0-9]+', '', 'g') LIKE %s
                    OR regexp_replace(COALESCE(s.whatsapp_number, ''), '[^0-9]+', '', 'g') LIKE %s
                )
            """
            score_clause = """
                CASE
                    WHEN regexp_replace(COALESCE(s.phone_number, ''), '[^0-9]+', '', 'g') = %s THEN 130
                    WHEN regexp_replace(COALESCE(s.whatsapp_number, ''), '[^0-9]+', '', 'g') = %s THEN 126
                    ELSE 96
                END
            """
            params = (digits, digits, digit_contains, digit_contains, limit)
        elif search_by == "TAZKIRA":
            where_clause = "s.tazkira_no ILIKE %s"
            score_clause = """
                CASE
                    WHEN LOWER(s.tazkira_no) = %s THEN 130
                    WHEN s.tazkira_no ILIKE %s THEN 112
                    ELSE 92
                END
            """
            params = (normalized, prefix, contains, limit)
        else:
            where_conditions = [
                "CAST(s.surveyor_id AS TEXT) = %s",
                "s.surveyor_code ILIKE %s",
                "s.surveyor_name ILIKE %s",
                "s.tazkira_no ILIKE %s",
            ]
            where_params: list[object] = [term, prefix, contains, contains]

            score_checks = [
                "WHEN CAST(s.surveyor_id AS TEXT) = %s THEN 145",
                "WHEN LOWER(s.surveyor_code) = %s THEN 136",
                "WHEN LOWER(s.surveyor_name) = %s THEN 128",
                "WHEN LOWER(s.tazkira_no) = %s THEN 122",
                "WHEN s.surveyor_code ILIKE %s THEN 112",
                "WHEN s.surveyor_name ILIKE %s THEN 102",
                "WHEN s.tazkira_no ILIKE %s THEN 96",
            ]
            score_params: list[object] = [term, normalized, normalized, normalized, prefix, prefix, prefix]

            if digits:
                where_conditions.extend(
                    [
                        "regexp_replace(COALESCE(s.phone_number, ''), '[^0-9]+', '', 'g') LIKE %s",
                        "regexp_replace(COALESCE(s.whatsapp_number, ''), '[^0-9]+', '', 'g') LIKE %s",
                    ]
                )
                where_params.extend([digit_contains, digit_contains])
                score_checks.extend(
                    [
                        "WHEN regexp_replace(COALESCE(s.phone_number, ''), '[^0-9]+', '', 'g') = %s THEN 118",
                        "WHEN regexp_replace(COALESCE(s.whatsapp_number, ''), '[^0-9]+', '', 'g') = %s THEN 114",
                        "WHEN regexp_replace(COALESCE(s.phone_number, ''), '[^0-9]+', '', 'g') LIKE %s THEN 94",
                        "WHEN regexp_replace(COALESCE(s.whatsapp_number, ''), '[^0-9]+', '', 'g') LIKE %s THEN 92",
                    ]
                )
                score_params.extend([digits, digits, digit_contains, digit_contains])

            where_clause = f"({' OR '.join(where_conditions)})"
            score_clause = "CASE " + " ".join(score_checks) + " ELSE 74 END"
            params = tuple(score_params + where_params + [limit])

        return fetch_all(
            f"""
            SELECT
            s.surveyor_id,
            s.surveyor_code,
            s.surveyor_name,
            s.tazkira_no,
            s.phone_number,
            s.whatsapp_number,
            {score_clause} AS match_score
            FROM surveyors s
            WHERE {where_clause}
            ORDER BY match_score DESC, s.surveyor_name ASC, s.surveyor_id DESC
            LIMIT %s
            """,
            params,
        )

    def get_by_id(self, surveyor_id: int) -> dict | None:
        return fetch_one("SELECT * FROM surveyors WHERE surveyor_id = %s", (surveyor_id,))

    def get_profile_detail(self, surveyor_id: int) -> dict | None:
        return fetch_one(
            f"""
            {self._PROFILE_SELECT},
            s.tazkira_image,
            s.tazkira_image_mime
            {self._PROFILE_FROM}
            WHERE s.surveyor_id = %s
            """,
            (surveyor_id,),
        )

    def next_sequence_for_province(self, province_code: str, *, connection=None) -> int:
        row = execute(
            """
            INSERT INTO province_sequences (province_code, last_number)
            VALUES (%s, %s)
            ON CONFLICT (province_code)
            DO UPDATE SET last_number = province_sequences.last_number + 1
            RETURNING last_number
            """,
            (province_code, 1),
            connection=connection,
            returning=True,
        )
        return int(row["last_number"])

    def create(self, payload: dict, *, connection=None) -> dict:
        return execute(
            """
            INSERT INTO surveyors (
                surveyor_code, surveyor_name, gender, father_name, tazkira_no,
                email_address, whatsapp_number, phone_number, permanent_province_code,
                current_province_code, cv_link, cv_file, cv_file_name, cv_mime,
                tazkira_image, tazkira_image_name, tazkira_image_mime,
                tazkira_pdf, tazkira_pdf_name, tazkira_pdf_mime,
                tazkira_word, tazkira_word_name, tazkira_word_mime
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                payload["surveyor_code"],
                payload["surveyor_name"],
                payload["gender"],
                payload["father_name"],
                payload["tazkira_no"],
                payload["email_address"],
                payload["whatsapp_number"],
                payload["phone_number"],
                payload["permanent_province_code"],
                payload["current_province_code"],
                payload["cv_link"],
                payload.get("cv_file"),
                payload.get("cv_file_name"),
                payload.get("cv_mime"),
                payload.get("tazkira_image"),
                payload.get("tazkira_image_name"),
                payload.get("tazkira_image_mime"),
                payload.get("tazkira_pdf"),
                payload.get("tazkira_pdf_name"),
                payload.get("tazkira_pdf_mime"),
                payload.get("tazkira_word"),
                payload.get("tazkira_word_name"),
                payload.get("tazkira_word_mime"),
            ),
            connection=connection,
            returning=True,
        )
