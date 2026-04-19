from app.core.database import execute, fetch_all, fetch_one, transaction


class ProjectRepository:
    def list_all(self, limit: int = 500) -> list[dict]:
        return fetch_all(
            """
            SELECT
                   p.project_id,
                   p.project_code,
                   p.project_name,
                   p.project_short_name,
                   p.phase_number,
                   p.project_type,
                   p.client_name,
                   p.implementing_partner,
                   p.start_date,
                   p.end_date,
                   p.status,
                   p.project_document_link,
                   p.created_at,
                   COALESCE(ps_counts.assignment_count, 0) AS assignment_count
            FROM projects p
            LEFT JOIN (
                SELECT project_id, COUNT(*)::int AS assignment_count
                FROM project_surveyors
                GROUP BY project_id
            ) ps_counts ON ps_counts.project_id = p.project_id
            ORDER BY p.project_id DESC
            LIMIT %s
            """,
            (limit,),
        )

    def get_by_id(self, project_id: int) -> dict | None:
        return fetch_one("SELECT * FROM projects WHERE project_id = %s", (project_id,))

    def get_phase_sequence(self, client_code: str, project_key: str, start_year: int | None) -> dict | None:
        return fetch_one(
            """
            SELECT *
            FROM project_phase_sequences
            WHERE client_code = %s
              AND project_key = %s
              AND start_year IS NOT DISTINCT FROM %s
            """,
            (client_code, project_key, start_year),
        )

    def reserve_next_phase_sequence(self, client_code: str, project_key: str, start_year: int | None, *, connection) -> int:
        execute(
            """
            SELECT pg_advisory_xact_lock(hashtext(%s))
            """,
            (f"{client_code}:{project_key}:{start_year if start_year is not None else 'none'}",),
            connection=connection,
        )
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT seq_id, last_phase
                FROM project_phase_sequences
                WHERE client_code = %s
                  AND project_key = %s
                  AND start_year IS NOT DISTINCT FROM %s
                FOR UPDATE
                """,
                (client_code, project_key, start_year),
            )
            row = cur.fetchone()

        if row:
            seq_id, last_phase = row
            next_phase = last_phase + 1
            execute(
                """
                UPDATE project_phase_sequences
                SET last_phase = %s
                WHERE seq_id = %s
                """,
                (next_phase, seq_id),
                connection=connection,
            )
            return next_phase

        execute(
            """
            INSERT INTO project_phase_sequences (client_code, project_key, last_phase, start_year)
            VALUES (%s, %s, %s, %s)
            """,
            (client_code, project_key, 1, start_year),
            connection=connection,
        )
        return 1

    def create(self, payload: dict, *, connection=None) -> dict:
        return execute(
            """
            INSERT INTO projects (
                project_code, project_name, phase_number, project_type, client_name,
                implementing_partner, start_date, end_date, status, notes,
                project_document_link, project_short_name
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                payload["project_code"],
                payload["project_name"],
                payload["phase_number"],
                payload["project_type"],
                payload["client_name"],
                payload["implementing_partner"],
                payload["start_date"],
                payload["end_date"],
                payload["status"],
                payload["notes"],
                payload["project_document_link"],
                payload["project_short_name"],
            ),
            connection=connection,
            returning=True,
        )

    def list_assignments(self, limit: int = 500) -> list[dict]:
        return fetch_all(
            """
            SELECT
                   ps.project_surveyor_id,
                   ps.project_id,
                   ps.surveyor_id,
                   ps.role,
                   ps.work_province_code,
                   ps.start_date,
                   ps.end_date,
                   ps.status,
                   p.project_name,
                   p.project_code,
                   s.surveyor_name,
                   s.surveyor_code,
                   pv.province_name AS work_province_name,
                   ARRAY_REMOVE(ARRAY_AGG(DISTINCT psp.province_code), NULL) AS extra_province_codes
            FROM project_surveyors ps
            JOIN projects p ON p.project_id = ps.project_id
            JOIN surveyors s ON s.surveyor_id = ps.surveyor_id
            LEFT JOIN provinces pv ON pv.province_code = ps.work_province_code
            LEFT JOIN project_surveyor_provinces psp ON psp.project_surveyor_id = ps.project_surveyor_id
            GROUP BY ps.project_surveyor_id, p.project_name, p.project_code, s.surveyor_name, s.surveyor_code, pv.province_name
            ORDER BY ps.project_surveyor_id DESC
            LIMIT %s
            """,
            (limit,),
        )

    def list_assignments_for_surveyor(self, surveyor_id: int, limit: int = 500) -> list[dict]:
        return fetch_all(
            """
            SELECT
                   ps.project_surveyor_id,
                   ps.project_id,
                   ps.surveyor_id,
                   ps.role,
                   ps.work_province_code,
                   ps.start_date AS assignment_start_date,
                   ps.end_date AS assignment_end_date,
                   ps.status AS assignment_status,
                   p.project_name,
                   p.project_code,
                   p.project_short_name,
                   p.project_type,
                   p.client_name,
                   p.implementing_partner,
                   p.start_date AS project_start_date,
                   p.end_date AS project_end_date,
                   p.status AS project_status,
                   pv.province_name AS work_province_name,
                   ARRAY_REMOVE(ARRAY_AGG(DISTINCT psp.province_code), NULL) AS extra_province_codes,
                   (
                       ps.status = 'ACTIVE'
                       AND p.status = 'ACTIVE'
                       AND ps.start_date <= CURRENT_DATE
                       AND (ps.end_date IS NULL OR ps.end_date >= CURRENT_DATE)
                   ) AS is_current_active
            FROM project_surveyors ps
            JOIN projects p ON p.project_id = ps.project_id
            LEFT JOIN provinces pv ON pv.province_code = ps.work_province_code
            LEFT JOIN project_surveyor_provinces psp ON psp.project_surveyor_id = ps.project_surveyor_id
            WHERE ps.surveyor_id = %s
            GROUP BY ps.project_surveyor_id, p.project_id, pv.province_name
            ORDER BY is_current_active DESC, ps.start_date DESC, ps.project_surveyor_id DESC
            LIMIT %s
            """,
            (surveyor_id, limit),
        )

    def list_assignment_conflicts(
        self,
        project_id: int,
        surveyor_ids: list[int],
        start_date,
        end_date,
        limit: int = 500,
    ) -> list[dict]:
        if not surveyor_ids or not start_date:
            return []
        return fetch_all(
            """
            SELECT
                   ps.project_surveyor_id,
                   ps.project_id,
                   ps.surveyor_id,
                   ps.role,
                   ps.status AS assignment_status,
                   ps.start_date AS assignment_start_date,
                   ps.end_date AS assignment_end_date,
                   ps.work_province_code,
                   p.project_name,
                   p.project_code,
                   s.surveyor_name,
                   s.surveyor_code,
                   pv.province_name AS work_province_name,
                   (ps.project_id = %s) AS same_project,
                   NOT (
                       COALESCE(ps.end_date, DATE '9999-12-31') < %s
                       OR COALESCE(%s, DATE '9999-12-31') < ps.start_date
                   ) AS overlaps_window
            FROM project_surveyors ps
            JOIN projects p ON p.project_id = ps.project_id
            JOIN surveyors s ON s.surveyor_id = ps.surveyor_id
            LEFT JOIN provinces pv ON pv.province_code = ps.work_province_code
            WHERE ps.surveyor_id = ANY(%s)
              AND (
                  ps.project_id = %s
                  OR NOT (
                      COALESCE(ps.end_date, DATE '9999-12-31') < %s
                      OR COALESCE(%s, DATE '9999-12-31') < ps.start_date
                  )
              )
            ORDER BY same_project DESC, overlaps_window DESC, s.surveyor_name ASC, ps.start_date DESC, ps.project_surveyor_id DESC
            LIMIT %s
            """,
            (project_id, start_date, end_date, surveyor_ids, project_id, start_date, end_date, limit),
        )

    def create_assignment(self, payload: dict) -> dict:
        created = self.create_assignments([payload])
        return created[0]

    def create_assignments(self, payloads: list[dict]) -> list[dict]:
        if not payloads:
            return []
        with transaction() as conn:
            created_assignments: list[dict] = []
            for payload in payloads:
                assignment = execute(
                    """
                    INSERT INTO project_surveyors (
                        project_id, surveyor_id, role, work_province_code, start_date, end_date, status, notes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        payload["project_id"],
                        payload["surveyor_id"],
                        payload["role"],
                        payload["work_province_code"],
                        payload["start_date"],
                        payload["end_date"],
                        payload["status"],
                        payload["notes"],
                    ),
                    connection=conn,
                    returning=True,
                )
                extra_provinces = payload.get("extra_province_codes", [])
                for province_code in extra_provinces:
                    execute(
                        """
                        INSERT INTO project_surveyor_provinces (project_surveyor_id, province_code)
                        VALUES (%s, %s)
                        ON CONFLICT (project_surveyor_id, province_code) DO NOTHING
                        """,
                        (assignment["project_surveyor_id"], province_code),
                        connection=conn,
                    )
                created_assignments.append(assignment)
            return created_assignments
