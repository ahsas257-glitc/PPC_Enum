import streamlit as st

from app.core.database import fetch_one, get_connection


DASHBOARD_CACHE_TTL_SECONDS = 120
_METRICS_QUERY = """
    SELECT
        (SELECT COUNT(*) FROM users) AS total_users,
        (SELECT COUNT(*) FROM users WHERE is_active = false) AS pending_users,
        (SELECT COUNT(*) FROM users WHERE is_active = true) AS active_users,
        (SELECT COUNT(*) FROM projects) AS total_projects,
        (SELECT COUNT(*) FROM projects WHERE status = 'ACTIVE') AS active_projects,
        (SELECT COUNT(*) FROM surveyors) AS total_surveyors,
        (SELECT COUNT(*) FROM surveyor_bank_accounts) AS total_bank_accounts,
        (SELECT COUNT(*) FROM surveyor_bank_accounts WHERE is_active = true) AS active_bank_accounts,
        (SELECT COUNT(*) FROM surveyor_bank_accounts WHERE payment_type = 'BANK_ACCOUNT') AS bank_account_channels,
        (SELECT COUNT(*) FROM surveyor_bank_accounts WHERE payment_type = 'MOBILE_CREDIT') AS mobile_money_channels,
        (SELECT COUNT(DISTINCT surveyor_id) FROM surveyor_bank_accounts) AS surveyors_with_accounts,
        (
            SELECT COUNT(*)
            FROM project_surveyors ps
            JOIN projects p ON p.project_id = ps.project_id
            WHERE ps.status = 'ACTIVE'
              AND p.status = 'ACTIVE'
              AND ps.start_date <= CURRENT_DATE
              AND (ps.end_date IS NULL OR ps.end_date >= CURRENT_DATE)
        ) AS current_assignments,
        (SELECT COUNT(*) FROM audit_log) AS total_audit_logs
"""


class DashboardRepository:
    def get_metrics(self) -> dict:
        return fetch_one(_METRICS_QUERY) or {}

    @st.cache_data(ttl=DASHBOARD_CACHE_TTL_SECONDS, show_spinner=False)
    def get_home_data(_self) -> dict:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_METRICS_QUERY)
                metric_columns = [column[0] for column in cur.description]
                metric_row = cur.fetchone()
                metrics = dict(zip(metric_columns, metric_row)) if metric_row else {}

                cur.execute(
                    """
                    SELECT
                        audit_id,
                        actor_role,
                        actor_name,
                        action,
                        entity,
                        entity_key,
                        created_at
                    FROM audit_log
                    ORDER BY created_at DESC, audit_id DESC
                    LIMIT 10
                    """
                )
                audit_columns = [column[0] for column in cur.description]
                audit_rows = [dict(zip(audit_columns, row)) for row in cur.fetchall()]

                cur.execute(
                    """
                    WITH day_window AS (
                        SELECT generate_series(
                            CURRENT_DATE - INTERVAL '13 days',
                            CURRENT_DATE,
                            INTERVAL '1 day'
                        )::date AS activity_day
                    )
                    SELECT
                        dw.activity_day,
                        COALESCE(COUNT(a.audit_id), 0)::int AS total
                    FROM day_window dw
                    LEFT JOIN audit_log a
                      ON a.created_at >= dw.activity_day
                     AND a.created_at < dw.activity_day + INTERVAL '1 day'
                    GROUP BY dw.activity_day
                    ORDER BY dw.activity_day
                    """
                )
                audit_trend_columns = [column[0] for column in cur.description]
                audit_trend = [dict(zip(audit_trend_columns, row)) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT
                        COALESCE(NULLIF(role::text, ''), 'UNASSIGNED') AS label,
                        COUNT(*)::int AS total
                    FROM users
                    GROUP BY 1
                    ORDER BY total DESC, label ASC
                    """
                )
                user_role_columns = [column[0] for column in cur.description]
                user_role_mix = [dict(zip(user_role_columns, row)) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT
                        COALESCE(NULLIF(status::text, ''), 'UNKNOWN') AS label,
                        COUNT(*)::int AS total
                    FROM projects
                    GROUP BY 1
                    ORDER BY total DESC, label ASC
                    """
                )
                project_status_columns = [column[0] for column in cur.description]
                project_status_mix = [dict(zip(project_status_columns, row)) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT
                        COALESCE(NULLIF(payment_type::text, ''), 'UNKNOWN') AS label,
                        COUNT(*)::int AS total
                    FROM surveyor_bank_accounts
                    GROUP BY 1
                    ORDER BY total DESC, label ASC
                    """
                )
                payment_type_columns = [column[0] for column in cur.description]
                payment_type_mix = [dict(zip(payment_type_columns, row)) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT
                        COALESCE(NULLIF(action, ''), 'SYSTEM') AS label,
                        COUNT(*)::int AS total
                    FROM audit_log
                    GROUP BY 1
                    ORDER BY total DESC, label ASC
                    LIMIT 6
                    """
                )
                action_columns = [column[0] for column in cur.description]
                action_mix = [dict(zip(action_columns, row)) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT
                        COALESCE(NULLIF(entity, ''), 'SYSTEM') AS label,
                        COUNT(*)::int AS total
                    FROM audit_log
                    GROUP BY 1
                    ORDER BY total DESC, label ASC
                    LIMIT 6
                    """
                )
                entity_columns = [column[0] for column in cur.description]
                entity_mix = [dict(zip(entity_columns, row)) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT
                        p.project_id,
                        p.project_code,
                        p.project_name,
                        p.client_name,
                        p.project_type,
                        p.start_date,
                        p.end_date,
                        p.status,
                        COALESCE(assignments.assignment_count, 0) AS assignment_count
                    FROM (
                        SELECT
                            project_id,
                            project_code,
                            project_name,
                            client_name,
                            project_type,
                            start_date,
                            end_date,
                            status
                        FROM projects
                        ORDER BY project_id DESC
                        LIMIT 8
                    ) p
                    LEFT JOIN LATERAL (
                        SELECT COUNT(*)::int AS assignment_count
                        FROM project_surveyors ps
                        WHERE ps.project_id = p.project_id
                    ) assignments ON true
                    ORDER BY p.project_id DESC
                    """
                )
                recent_project_columns = [column[0] for column in cur.description]
                recent_projects = [dict(zip(recent_project_columns, row)) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT
                        s.surveyor_id,
                        s.surveyor_code,
                        s.surveyor_name,
                        cp.province_name AS current_province_name,
                        pp.province_name AS permanent_province_name,
                        (
                            (s.cv_file IS NOT NULL)::int +
                            (s.tazkira_image IS NOT NULL)::int +
                            (s.tazkira_pdf IS NOT NULL)::int +
                            (s.tazkira_word IS NOT NULL)::int
                        ) AS document_count,
                        COALESCE(accounts.account_count, 0) AS account_count
                    FROM surveyors s
                    LEFT JOIN provinces cp ON cp.province_code = s.current_province_code
                    LEFT JOIN provinces pp ON pp.province_code = s.permanent_province_code
                    LEFT JOIN LATERAL (
                        SELECT COUNT(*)::int AS account_count
                        FROM surveyor_bank_accounts sba
                        WHERE sba.surveyor_id = s.surveyor_id
                    ) accounts ON true
                    ORDER BY s.surveyor_id DESC
                    LIMIT 8
                    """
                )
                recent_surveyor_columns = [column[0] for column in cur.description]
                recent_surveyors = [dict(zip(recent_surveyor_columns, row)) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT
                        p.project_code AS label,
                        COUNT(ps.project_surveyor_id)::int AS total
                    FROM project_surveyors ps
                    JOIN projects p ON p.project_id = ps.project_id
                    WHERE ps.status = 'ACTIVE'
                      AND p.status = 'ACTIVE'
                      AND ps.start_date <= CURRENT_DATE
                      AND (ps.end_date IS NULL OR ps.end_date >= CURRENT_DATE)
                    GROUP BY p.project_code
                    ORDER BY total DESC, label ASC
                    LIMIT 8
                    """
                )
                project_load_columns = [column[0] for column in cur.description]
                project_load_mix = [dict(zip(project_load_columns, row)) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT
                        COALESCE(cp.province_name, 'Unknown') AS label,
                        COUNT(*)::int AS total
                    FROM surveyors s
                    LEFT JOIN provinces cp ON cp.province_code = s.current_province_code
                    GROUP BY 1
                    ORDER BY total DESC, label ASC
                    LIMIT 8
                    """
                )
                surveyor_province_columns = [column[0] for column in cur.description]
                surveyor_province_mix = [dict(zip(surveyor_province_columns, row)) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT
                        COALESCE(NULLIF(client_name, ''), 'Unknown Client') AS label,
                        COUNT(*)::int AS total
                    FROM projects
                    GROUP BY 1
                    ORDER BY total DESC, label ASC
                    LIMIT 8
                    """
                )
                client_columns = [column[0] for column in cur.description]
                client_mix = [dict(zip(client_columns, row)) for row in cur.fetchall()]

        return {
            "metrics": metrics,
            "recent_audit": audit_rows,
            "audit_trend": audit_trend,
            "user_role_mix": user_role_mix,
            "project_status_mix": project_status_mix,
            "payment_type_mix": payment_type_mix,
            "action_mix": action_mix,
            "entity_mix": entity_mix,
            "recent_projects": recent_projects,
            "recent_surveyors": recent_surveyors,
            "project_load_mix": project_load_mix,
            "surveyor_province_mix": surveyor_province_mix,
            "client_mix": client_mix,
        }
