from __future__ import annotations

import base64
from functools import lru_cache
from html import escape

import pandas as pd
import streamlit as st

from app.core.session import get_current_user
from app.design.components.tables import render_table
from app.design.theme import LOGO_FILE
from app.services.dashboard_service import DashboardService

_FULL_ACCESS_ROLES = {"super_admin"}


@lru_cache(maxsize=1)
def _dashboard_logo_src() -> str:
    if not LOGO_FILE.exists():
        return ""
    encoded = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _percent(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return round((numerator / denominator) * 100)


def _format_compact_number(value: object) -> str:
    amount = _safe_int(value)
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"{amount / 1_000:.1f}K"
    return f"{amount:,}"


def _humanize_token(value: object) -> str:
    token = str(value or "").strip().replace("_", " ")
    return token.title() if token else "Unknown"


def _mix_frame(rows: list[dict], *, limit: int = 8) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["label", "total"])
    frame = frame.copy()
    frame["label"] = frame["label"].map(_humanize_token)
    frame["total"] = pd.to_numeric(frame["total"], errors="coerce").fillna(0).astype(int)
    frame = frame.sort_values(["total", "label"], ascending=[False, True]).head(limit)
    return frame.reset_index(drop=True)


def _audit_trend_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["day", "day_label", "total"])
    frame = frame.copy()
    frame["activity_day"] = pd.to_datetime(frame["activity_day"])
    frame["day"] = frame["activity_day"].dt.strftime("%Y-%m-%d")
    frame["day_label"] = frame["activity_day"].dt.strftime("%b %d")
    frame["total"] = pd.to_numeric(frame["total"], errors="coerce").fillna(0).astype(int)
    return frame[["day", "day_label", "total"]]


def _recent_projects_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    columns = [
        "project_code",
        "project_name",
        "client_name",
        "project_type",
        "status",
        "assignment_count",
        "start_date",
        "end_date",
    ]
    return frame[columns]


def _recent_surveyors_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    columns = [
        "surveyor_code",
        "surveyor_name",
        "current_province_name",
        "permanent_province_name",
        "document_count",
        "account_count",
    ]
    return frame[columns]


def _scope_config(role: str) -> dict[str, str]:
    if role in _FULL_ACCESS_ROLES:
        return {
            "title": "Executive operations command center",
            "description": "Platform-wide oversight across users, projects, surveyors, payouts, and audit movement.",
            "badge": "Full control",
            "mode": "Full visibility",
        }
    return {
        "title": "Field operations overview",
        "description": "A focused workspace for project delivery, surveyor coverage, and live operational capacity.",
        "badge": "Summary mode",
        "mode": "Scoped visibility",
    }


def _metric_chip_markup(label: str, value: object, tone: str = "default") -> str:
    return (
        f'<div class="dashboard-metric-chip dashboard-metric-chip--{escape(tone)}">'
        f'<span>{escape(label)}</span>'
        f"<strong>{escape(_format_compact_number(value))}</strong>"
        "</div>"
    )


def _health_rail_markup(label: str, percent_value: int, detail: str, tone: str) -> str:
    bounded_value = max(0, min(percent_value, 100))
    return f"""
    <div class="dashboard-health-rail dashboard-health-rail--{escape(tone)}">
        <div class="dashboard-health-rail__row">
            <span>{escape(label)}</span>
            <strong>{escape(str(bounded_value))}%</strong>
        </div>
        <div class="dashboard-health-rail__track">
            <div class="dashboard-health-rail__fill" style="width:{bounded_value}%"></div>
        </div>
        <small>{escape(detail)}</small>
    </div>
    """


def _panel_header_html(title: str, meta: str, *, eyebrow: str, pills: list[str] | None = None) -> str:
    pill_markup = "".join(f"<span>{escape(pill)}</span>" for pill in (pills or []) if pill)
    return f"""
    <div class="dashboard-panel-head">
        <div class="dashboard-panel-head__copy">
            <div class="dashboard-panel-head__eyebrow">{escape(eyebrow)}</div>
            <h3 title="{escape(title)}">{escape(title)}</h3>
            <p>{escape(meta)}</p>
        </div>
        <div class="dashboard-panel-head__pills">{pill_markup}</div>
    </div>
    """


def _build_command_deck_html(metrics: dict[str, object], role: str) -> str:
    config = _scope_config(role)
    total_users = _safe_int(metrics.get("total_users"))
    active_users = _safe_int(metrics.get("active_users"))
    pending_users = _safe_int(metrics.get("pending_users"))
    total_projects = _safe_int(metrics.get("total_projects"))
    active_projects = _safe_int(metrics.get("active_projects"))
    total_surveyors = _safe_int(metrics.get("total_surveyors"))
    surveyors_with_accounts = _safe_int(metrics.get("surveyors_with_accounts"))
    current_assignments = _safe_int(metrics.get("current_assignments"))
    total_bank_accounts = _safe_int(metrics.get("total_bank_accounts"))
    approval_rate = _percent(active_users, total_users)
    project_live_rate = _percent(active_projects, total_projects)
    payout_coverage = _percent(surveyors_with_accounts, total_surveyors)
    payout_mix_share = _percent(_safe_int(metrics.get("bank_account_channels")), total_bank_accounts)
    logo_src = _dashboard_logo_src()
    logo_markup = (
        f'<img class="dashboard-command-deck__logo" src="{logo_src}" alt="PPC logo">'
        if logo_src
        else '<div class="dashboard-command-deck__logo-fallback">PPC</div>'
    )

    top_metrics = "".join(
        [
            _metric_chip_markup("Projects", total_projects, "primary"),
            _metric_chip_markup("Surveyors", total_surveyors, "mint"),
            _metric_chip_markup("Assignments", current_assignments, "cool"),
            _metric_chip_markup("Payout Channels", total_bank_accounts, "warm"),
        ]
    )

    if role in _FULL_ACCESS_ROLES:
        top_metrics += _metric_chip_markup("Users", total_users, "default")
        top_metrics += _metric_chip_markup("Audit Trail", metrics.get("total_audit_logs", 0), "default")

    rails_markup = "".join(
        [
            _health_rail_markup(
                "Project live rate",
                project_live_rate,
                f"{active_projects:,} active projects out of {total_projects:,}",
                "primary",
            ),
            _health_rail_markup(
                "Surveyor payout coverage",
                payout_coverage,
                f"{surveyors_with_accounts:,} surveyors linked to payout channels",
                "mint",
            ),
            _health_rail_markup(
                "Bank-first routing",
                payout_mix_share,
                f"{_safe_int(metrics.get('bank_account_channels')):,} bank channels across {total_bank_accounts:,} total records",
                "warm",
            ),
            _health_rail_markup(
                "Account approval readiness",
                approval_rate,
                f"{active_users:,} active users with {pending_users:,} pending approvals",
                "cool",
            ),
        ]
    )

    return f"""
    <section class="dashboard-command-deck">
        <div class="dashboard-command-deck__main">
            <div class="dashboard-command-deck__eyebrow">Dashboard</div>
            <h2 title="{escape(config['title'])}">{escape(config['title'])}</h2>
            <p>{escape(config['description'])}</p>
            <div class="dashboard-command-deck__chips">{top_metrics}</div>
        </div>
        <div class="dashboard-command-deck__brand">
            <div class="dashboard-command-deck__brand-row">
                {logo_markup}
                <div class="dashboard-command-deck__badge">{escape(config['badge'])}</div>
            </div>
            <div class="dashboard-command-deck__glance">
                <div>
                    <span>Current assignments</span>
                    <strong>{escape(_format_compact_number(current_assignments))}</strong>
                </div>
                <div>
                    <span>Active projects</span>
                    <strong>{escape(_format_compact_number(active_projects))}</strong>
                </div>
                <div>
                    <span>Payout coverage</span>
                    <strong>{escape(str(payout_coverage))}%</strong>
                </div>
                <div>
                    <span>Visibility mode</span>
                    <strong>{escape(config['mode'])}</strong>
                </div>
            </div>
            <div class="dashboard-command-deck__rails">{rails_markup}</div>
        </div>
    </section>
    """


def _build_health_html(metrics: dict[str, object]) -> str:
    items = [
        ("Pending approvals", metrics.get("pending_users", 0), "Accounts waiting for review"),
        ("Live projects", metrics.get("active_projects", 0), "Projects with active status"),
        ("Current assignments", metrics.get("current_assignments", 0), "Assignments inside the active date window"),
        ("Surveyors linked", metrics.get("surveyors_with_accounts", 0), "Surveyors with payout channels"),
        ("Active payout", metrics.get("active_bank_accounts", 0), "Channels available for disbursement"),
        ("Mobile money", metrics.get("mobile_money_channels", 0), "Channels routed through mobile credit"),
    ]
    cards = "".join(
        f"""
        <div class="dashboard-signal-card">
            <span>{escape(label)}</span>
            <strong>{escape(_format_compact_number(value))}</strong>
            <small>{escape(description)}</small>
        </div>
        """
        for label, value, description in items
    )
    return f'<div class="dashboard-signal-grid">{cards}</div>'


def _build_spotlight_html(
    action_mix: pd.DataFrame,
    entity_mix: pd.DataFrame,
    recent_audit: list[dict],
) -> str:
    def _list_markup(title: str, frame: pd.DataFrame) -> str:
        if frame.empty:
            items = '<div class="dashboard-spotlight-list__empty">No activity yet.</div>'
        else:
            items = "".join(
                f"""
                <div class="dashboard-spotlight-list__item">
                    <span title="{escape(str(row.label))}">{escape(str(row.label))}</span>
                    <strong>{escape(_format_compact_number(row.total))}</strong>
                </div>
                """
                for row in frame.itertuples(index=False)
            )
        return f"""
        <div class="dashboard-spotlight-list">
            <h4 title="{escape(title)}">{escape(title)}</h4>
            {items}
        </div>
        """

    latest_rows = recent_audit[:4]
    if latest_rows:
        feed_markup = "".join(
            f"""
            <div class="dashboard-feed-row">
                <div>
                    <span title="{escape(_humanize_token(item.get('entity')))}">{escape(_humanize_token(item.get("entity")))}</span>
                    <strong title="{escape(_humanize_token(item.get('action')))}">{escape(_humanize_token(item.get("action")))}</strong>
                </div>
                <small>{escape(str(item.get("actor_name") or "System"))}</small>
            </div>
            """
            for item in latest_rows
        )
    else:
        feed_markup = '<div class="dashboard-spotlight-list__empty">No recent activity yet.</div>'

    return (
        _list_markup("Action pressure", action_mix)
        + _list_markup("Entity pressure", entity_mix)
        + f'<div class="dashboard-feed"><h4 title="Latest moves">Latest moves</h4>{feed_markup}</div>'
    )


def _time_series_spec(frame: pd.DataFrame) -> dict:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "height": 284,
        "data": {"values": frame.to_dict(orient="records")},
        "layer": [
            {
                "mark": {
                    "type": "area",
                    "interpolate": "monotone",
                    "line": {"color": "#79dcff", "strokeWidth": 2.4},
                    "color": {
                        "gradient": "linear",
                        "x1": 1,
                        "x2": 1,
                        "y1": 1,
                        "y2": 0,
                        "stops": [
                            {"offset": 0, "color": "rgba(121,220,255,0.03)"},
                            {"offset": 1, "color": "rgba(121,220,255,0.30)"},
                        ],
                    },
                },
                "encoding": {
                    "x": {
                        "field": "day",
                        "type": "temporal",
                        "title": None,
                        "axis": {
                            "labelColor": "rgba(220,236,250,0.66)",
                            "labelAngle": 0,
                            "labelPadding": 10,
                            "grid": False,
                            "tickColor": "rgba(151,192,230,0.18)",
                            "domain": False,
                            "format": "%b %d",
                        },
                    },
                    "y": {
                        "field": "total",
                        "type": "quantitative",
                        "title": None,
                        "axis": {
                            "labelColor": "rgba(220,236,250,0.66)",
                            "gridColor": "rgba(151,192,230,0.12)",
                            "tickColor": "rgba(151,192,230,0.18)",
                            "domain": False,
                        },
                    },
                    "tooltip": [
                        {"field": "day_label", "type": "nominal", "title": "Day"},
                        {"field": "total", "type": "quantitative", "title": "Audit events"},
                    ],
                },
            },
            {
                "mark": {
                    "type": "point",
                    "filled": True,
                    "size": 56,
                    "color": "#87f1e3",
                    "stroke": "#07111b",
                    "strokeWidth": 1.2,
                },
                "encoding": {
                    "x": {"field": "day", "type": "temporal"},
                    "y": {"field": "total", "type": "quantitative"},
                    "opacity": {"value": 0.9},
                    "tooltip": [
                        {"field": "day_label", "type": "nominal", "title": "Day"},
                        {"field": "total", "type": "quantitative", "title": "Audit events"},
                    ],
                },
            },
        ],
        "config": {
            "background": "transparent",
            "view": {"stroke": None},
            "axis": {"labelFont": "Inter", "titleFont": "Inter"},
        },
    }


def _distribution_spec(frame: pd.DataFrame, *, accent_color: str) -> dict:
    sorted_frame = frame.sort_values(["total", "label"], ascending=[True, False]).reset_index(drop=True)
    chart_height = max(180, min(340, 42 * max(len(sorted_frame), 1)))
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "height": chart_height,
        "data": {"values": sorted_frame.to_dict(orient="records")},
        "layer": [
            {
                "mark": {"type": "bar", "cornerRadiusEnd": 8, "height": 20},
                "encoding": {
                    "y": {
                        "field": "label",
                        "type": "nominal",
                        "sort": None,
                        "title": None,
                        "axis": {
                            "labelColor": "rgba(220,236,250,0.72)",
                            "domain": False,
                            "ticks": False,
                            "labelPadding": 10,
                        },
                    },
                    "x": {
                        "field": "total",
                        "type": "quantitative",
                        "title": None,
                        "axis": {
                            "labelColor": "rgba(220,236,250,0.62)",
                            "gridColor": "rgba(151,192,230,0.10)",
                            "domain": False,
                            "tickColor": "rgba(151,192,230,0.16)",
                        },
                    },
                    "color": {"value": accent_color},
                    "tooltip": [
                        {"field": "label", "type": "nominal", "title": "Segment"},
                        {"field": "total", "type": "quantitative", "title": "Count"},
                    ],
                },
            },
            {
                "mark": {
                    "type": "text",
                    "align": "left",
                    "baseline": "middle",
                    "dx": 8,
                    "color": "#f5fbff",
                    "fontSize": 12,
                    "fontWeight": 700,
                },
                "encoding": {
                    "y": {"field": "label", "type": "nominal", "sort": None},
                    "x": {"field": "total", "type": "quantitative"},
                    "text": {"field": "total", "type": "quantitative"},
                },
            },
        ],
        "config": {
            "background": "transparent",
            "view": {"stroke": None},
            "axis": {"labelFont": "Inter", "titleFont": "Inter"},
        },
    }


def _render_chart_panel(
    *,
    key: str,
    title: str,
    meta: str,
    eyebrow: str,
    frame: pd.DataFrame,
    spec: dict | None,
    pills: list[str] | None = None,
    empty_message: str = "No chart data available yet.",
) -> None:
    with st.container(key=key):
        st.html(_panel_header_html(title, meta, eyebrow=eyebrow, pills=pills))
        if frame.empty or spec is None:
            st.info(empty_message)
        else:
            st.vega_lite_chart(spec, width="stretch")


def _render_table_panel(
    *,
    key: str,
    title: str,
    meta: str,
    eyebrow: str,
    frame: pd.DataFrame,
    pills: list[str] | None = None,
    empty_message: str = "No data available yet.",
    max_visible_rows: int = 8,
) -> None:
    with st.container(key=key):
        st.html(_panel_header_html(title, meta, eyebrow=eyebrow, pills=pills))
        if frame.empty:
            st.info(empty_message)
        else:
            render_table(frame, max_visible_rows=max_visible_rows, row_height=38)


def render_dashboard_page() -> None:
    current_user = get_current_user() or {}
    role = str(current_user.get("role") or "viewer")
    full_view = role in _FULL_ACCESS_ROLES

    service = DashboardService()
    home_data = service.get_home_data()
    metrics = home_data.get("metrics", {})

    audit_rows = home_data.get("recent_audit", [])
    audit_trend = _audit_trend_frame(home_data.get("audit_trend", []))
    user_role_mix = _mix_frame(home_data.get("user_role_mix", []))
    project_status_mix = _mix_frame(home_data.get("project_status_mix", []))
    payment_type_mix = _mix_frame(home_data.get("payment_type_mix", []))
    action_mix = _mix_frame(home_data.get("action_mix", []), limit=6)
    entity_mix = _mix_frame(home_data.get("entity_mix", []), limit=6)
    project_load_mix = _mix_frame(home_data.get("project_load_mix", []), limit=8)
    surveyor_province_mix = _mix_frame(home_data.get("surveyor_province_mix", []), limit=8)
    client_mix = _mix_frame(home_data.get("client_mix", []), limit=8)
    recent_projects = _recent_projects_frame(home_data.get("recent_projects", []))
    recent_surveyors = _recent_surveyors_frame(home_data.get("recent_surveyors", []))

    st.html(_build_command_deck_html(metrics, role))

    overview_left, overview_right = st.columns([1.12, 1], gap="large")
    with overview_left:
        _render_chart_panel(
            key="dashboard_panel_project_load",
            title="Project deployment load",
            meta="Active assignment concentration by project code.",
            eyebrow="Projects",
            frame=project_load_mix,
            spec=_distribution_spec(project_load_mix, accent_color="#6aa8ff") if not project_load_mix.empty else None,
            pills=[
                f"{_format_compact_number(metrics.get('current_assignments'))} active assignments",
                f"{len(project_load_mix):,} live project bands",
            ],
            empty_message="Project deployment load will appear after assignments are created.",
        )
    with overview_right:
        _render_chart_panel(
            key="dashboard_panel_surveyor_coverage",
            title="Surveyor geographic coverage",
            meta="Current province distribution across the surveyor network.",
            eyebrow="Surveyors",
            frame=surveyor_province_mix,
            spec=_distribution_spec(surveyor_province_mix, accent_color="#87f1e3") if not surveyor_province_mix.empty else None,
            pills=[
                f"{_format_compact_number(metrics.get('total_surveyors'))} surveyors",
                f"{len(surveyor_province_mix):,} province bands",
            ],
            empty_message="Surveyor coverage will appear after surveyors are added.",
        )

    portfolio_left, portfolio_right = st.columns([1.12, 1], gap="large")
    with portfolio_left:
        _render_chart_panel(
            key="dashboard_panel_client_mix",
            title="Client portfolio concentration",
            meta="Project portfolio split across client accounts.",
            eyebrow="Portfolio",
            frame=client_mix,
            spec=_distribution_spec(client_mix, accent_color="#79dcff") if not client_mix.empty else None,
            pills=[f"{_format_compact_number(metrics.get('total_projects'))} total projects"],
            empty_message="Client concentration will appear after projects are registered.",
        )
    with portfolio_right:
        _render_chart_panel(
            key="dashboard_panel_project_status",
            title="Project lifecycle distribution",
            meta="Current spread of project statuses across the workspace.",
            eyebrow="Status",
            frame=project_status_mix,
            spec=_distribution_spec(project_status_mix, accent_color="#5fb3ff") if not project_status_mix.empty else None,
            pills=[f"{_format_compact_number(metrics.get('active_projects'))} active projects"],
            empty_message="Project lifecycle data will appear after projects are created.",
        )

    project_table_col, surveyor_table_col = st.columns(2, gap="large")
    with project_table_col:
        _render_table_panel(
            key="dashboard_panel_recent_projects",
            title="Recent projects",
            meta="Latest project records with client, status, and assignment volume.",
            eyebrow="Projects",
            frame=recent_projects,
            pills=[f"{len(recent_projects):,} rows loaded"],
            empty_message="Recent project records will appear here.",
            max_visible_rows=8,
        )
    with surveyor_table_col:
        _render_table_panel(
            key="dashboard_panel_recent_surveyors",
            title="Recent surveyors",
            meta="Newest surveyor records with province, dossier readiness, and payout linkage.",
            eyebrow="Surveyors",
            frame=recent_surveyors,
            pills=[f"{len(recent_surveyors):,} rows loaded"],
            empty_message="Recent surveyor records will appear here.",
            max_visible_rows=8,
        )

    if full_view:
        governance_left, governance_right = st.columns([1.18, 1], gap="large")
        with governance_left:
            _render_chart_panel(
                key="dashboard_panel_audit_flow",
                title="Audit activity timeline",
                meta="Daily audit event flow across the last fourteen days.",
                eyebrow="Audit",
                frame=audit_trend,
                spec=_time_series_spec(audit_trend) if not audit_trend.empty else None,
                pills=[
                    f"{_format_compact_number(metrics.get('total_audit_logs'))} total logs",
                    f"{audit_trend['total'].sum():,} events in window" if not audit_trend.empty else "No recent events",
                ],
                empty_message="Audit activity will appear here once records start landing in the log.",
            )
        with governance_right:
            with st.container(key="dashboard_panel_system_health"):
                st.html(
                    _panel_header_html(
                        "Platform governance signals",
                        "Super-admin health counters across approvals, payouts, and live workload.",
                        eyebrow="Governance",
                        pills=[
                            f"{_format_compact_number(metrics.get('pending_users'))} pending users",
                            f"{_format_compact_number(metrics.get('active_bank_accounts'))} active payout channels",
                        ],
                    )
                )
                st.html(_build_health_html(metrics))

        governance_mix_col, payout_col, spotlight_col = st.columns(3, gap="large")
        with governance_mix_col:
            _render_chart_panel(
                key="dashboard_panel_roles",
                title="User access distribution",
                meta="Role spread across all registered users in the system.",
                eyebrow="Users",
                frame=user_role_mix,
                spec=_distribution_spec(user_role_mix, accent_color="#79dcff") if not user_role_mix.empty else None,
                pills=[f"{_format_compact_number(metrics.get('total_users'))} users"],
                empty_message="User role distribution will appear after accounts are created.",
            )
        with payout_col:
            _render_chart_panel(
                key="dashboard_panel_payouts",
                title="Payout channel distribution",
                meta="Split between bank account routing and mobile money routing.",
                eyebrow="Payout",
                frame=payment_type_mix,
                spec=_distribution_spec(payment_type_mix, accent_color="#87f1e3") if not payment_type_mix.empty else None,
                pills=[f"{_format_compact_number(metrics.get('total_bank_accounts'))} payout channels"],
                empty_message="Payout mix will appear after payout accounts are registered.",
            )
        with spotlight_col:
            with st.container(key="dashboard_panel_spotlight"):
                st.html(
                    _panel_header_html(
                        "Activity spotlight",
                        "Most frequent audit actions, hottest entities, and latest named actors.",
                        eyebrow="Spotlight",
                        pills=[
                            f"{len(action_mix):,} top actions",
                            f"{len(entity_mix):,} top entities",
                        ],
                    )
                )
                st.html(_build_spotlight_html(action_mix, entity_mix, audit_rows))

        _render_table_panel(
            key="dashboard_panel_recent_activity",
            title="Recent audit records",
            meta="Latest actor, action, role, and entity combinations recorded in the audit trail.",
            eyebrow="Audit",
            frame=pd.DataFrame(audit_rows)[["created_at", "actor_name", "actor_role", "action", "entity", "entity_key"]] if audit_rows else pd.DataFrame(),
            pills=[f"{len(audit_rows):,} rows loaded"],
            empty_message="No audit activity yet.",
            max_visible_rows=10,
        )
