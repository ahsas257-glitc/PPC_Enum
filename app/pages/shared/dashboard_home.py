from __future__ import annotations

import base64
from functools import lru_cache
from html import escape

import pandas as pd
import streamlit as st

from app.core.session import get_current_user
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


def _format_date(value: object) -> str:
    if value is None:
        return "No date"
    if isinstance(value, str) and not value.strip():
        return "No date"
    try:
        if pd.isna(value):
            return "No date"
    except (TypeError, ValueError):
        pass
    try:
        timestamp = pd.to_datetime(value)
    except (TypeError, ValueError):
        return str(value)
    if pd.isna(timestamp):
        return "No date"
    return timestamp.strftime("%b %d, %Y")


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
            "title": "Operations command center",
            "description": "Users, projects, surveyors, payouts, and audit flow.",
            "badge": "Full control",
            "mode": "Full view",
        }
    return {
        "title": "Field operations overview",
        "description": "Projects, surveyor coverage, and live capacity.",
        "badge": "Summary mode",
        "mode": "Scoped view",
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


def _build_bar_chart_html(frame: pd.DataFrame, *, accent_color: str) -> str:
    if frame.empty:
        return ""

    rows = frame.head(8).to_dict(orient="records")
    max_total = max((_safe_int(row.get("total")) for row in rows), default=0) or 1
    row_markup = []
    for row in rows:
        label = str(row.get("label") or "Unknown")
        total = _safe_int(row.get("total"))
        width = 2 if total <= 0 else max(8, round((total / max_total) * 100))
        row_markup.append(
            f"""
            <div class="dashboard-bar-row" aria-label="{escape(label)}: {escape(str(total))}">
                <div class="dashboard-bar-row__top">
                    <span title="{escape(label)}">{escape(label)}</span>
                    <strong>{escape(_format_compact_number(total))}</strong>
                </div>
                <div class="dashboard-bar-track">
                    <div class="dashboard-bar-fill" style="width:{width}%"></div>
                </div>
            </div>
            """
        )

    return (
        f'<div class="dashboard-lite-chart dashboard-bar-chart" '
        f'style="--chart-accent:{escape(accent_color)}">'
        f'{"".join(row_markup)}</div>'
    )


def _build_trend_chart_html(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""

    rows = frame.tail(14).to_dict(orient="records")
    max_total = max((_safe_int(row.get("total")) for row in rows), default=0) or 1
    bars = []
    for row in rows:
        label = str(row.get("day_label") or row.get("day") or "")
        total = _safe_int(row.get("total"))
        height = 4 if total <= 0 else max(10, round((total / max_total) * 100))
        bars.append(
            f"""
            <div class="dashboard-trend-item" aria-label="{escape(label)}: {escape(str(total))}">
                <div class="dashboard-trend-bar" style="height:{height}%"></div>
                <strong>{escape(_format_compact_number(total))}</strong>
                <span>{escape(label)}</span>
            </div>
            """
        )

    return f'<div class="dashboard-lite-chart dashboard-trend-chart">{"".join(bars)}</div>'


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
            _metric_chip_markup("Payouts", total_bank_accounts, "warm"),
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
                f"{active_projects:,} active of {total_projects:,}",
                "primary",
            ),
            _health_rail_markup(
                "Payout coverage",
                payout_coverage,
                f"{surveyors_with_accounts:,} surveyors linked",
                "mint",
            ),
            _health_rail_markup(
                "Bank routing",
                payout_mix_share,
                f"{_safe_int(metrics.get('bank_account_channels')):,} bank of {total_bank_accounts:,}",
                "warm",
            ),
            _health_rail_markup(
                "Approval readiness",
                approval_rate,
                f"{active_users:,} active / {pending_users:,} pending",
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
                    <span>Assignments</span>
                    <strong>{escape(_format_compact_number(current_assignments))}</strong>
                </div>
                <div>
                    <span>Active</span>
                    <strong>{escape(_format_compact_number(active_projects))}</strong>
                </div>
                <div>
                    <span>Coverage</span>
                    <strong>{escape(str(payout_coverage))}%</strong>
                </div>
                <div>
                    <span>Mode</span>
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


def _status_tone(value: object) -> str:
    token = str(value or "").strip().lower().replace("_", "-")
    if token in {"active", "approved", "complete", "completed"}:
        return "active"
    if token in {"planned", "pending", "draft"}:
        return "pending"
    if token in {"on-hold", "hold", "paused"}:
        return "hold"
    if token in {"closed", "inactive", "rejected"}:
        return "closed"
    return "neutral"


def _build_project_stream_html(frame: pd.DataFrame) -> str:
    if frame.empty:
        return '<div class="dashboard-empty-state">Recent project records will appear here.</div>'

    cards = []
    for item in frame.head(5).to_dict(orient="records"):
        project_name = str(item.get("project_name") or "Untitled project")
        project_code = str(item.get("project_code") or "No code")
        client = str(item.get("client_name") or "Unassigned client")
        project_type = _humanize_token(item.get("project_type"))
        status = _humanize_token(item.get("status"))
        assignment_count = _format_compact_number(item.get("assignment_count"))
        timeline = f"{_format_date(item.get('start_date'))} - {_format_date(item.get('end_date'))}"
        cards.append(
            f"""
            <article class="dashboard-project-card">
                <div class="dashboard-project-card__main">
                    <span class="dashboard-code-pill">{escape(project_code)}</span>
                    <strong title="{escape(project_name)}">{escape(project_name)}</strong>
                    <small title="{escape(client)}">{escape(client)}</small>
                </div>
                <div class="dashboard-project-card__side">
                    <span class="dashboard-status-pill dashboard-status-pill--{escape(_status_tone(item.get('status')))}">
                        {escape(status)}
                    </span>
                    <div class="dashboard-project-card__meta">
                        <span>{escape(assignment_count)} assignments</span>
                        <span>{escape(project_type)}</span>
                    </div>
                </div>
                <div class="dashboard-project-card__timeline">{escape(timeline)}</div>
            </article>
            """
        )
    return f'<div class="dashboard-project-stream">{"".join(cards)}</div>'


def _build_surveyor_stream_html(frame: pd.DataFrame) -> str:
    if frame.empty:
        return '<div class="dashboard-empty-state">Recent surveyor records will appear here.</div>'

    cards = []
    for item in frame.head(6).to_dict(orient="records"):
        surveyor_name = str(item.get("surveyor_name") or "Unnamed surveyor")
        surveyor_code = str(item.get("surveyor_code") or "No code")
        current_province = str(item.get("current_province_name") or "Province not set")
        permanent_province = str(item.get("permanent_province_name") or "Permanent province not set")
        document_count = min(max(_safe_int(item.get("document_count")), 0), 4)
        account_count = _safe_int(item.get("account_count"))
        document_percent = _percent(document_count, 4)
        cards.append(
            f"""
            <article class="dashboard-surveyor-card">
                <div class="dashboard-surveyor-card__top">
                    <span class="dashboard-code-pill">{escape(surveyor_code)}</span>
                    <strong title="{escape(surveyor_name)}">{escape(surveyor_name)}</strong>
                </div>
                <div class="dashboard-surveyor-card__place">
                    <span title="{escape(current_province)}">{escape(current_province)}</span>
                    <small title="{escape(permanent_province)}">{escape(permanent_province)}</small>
                </div>
                <div class="dashboard-surveyor-card__rail">
                    <div class="dashboard-health-rail__track">
                        <div class="dashboard-health-rail__fill" style="width:{document_percent}%"></div>
                    </div>
                    <span>{document_count}/4 docs</span>
                </div>
                <div class="dashboard-surveyor-card__foot">{escape(_format_compact_number(account_count))} payout channel(s)</div>
            </article>
            """
        )
    return f'<div class="dashboard-surveyor-grid">{"".join(cards)}</div>'


def _build_audit_stream_html(rows: list[dict]) -> str:
    if not rows:
        return '<div class="dashboard-empty-state">No audit activity yet.</div>'

    items = []
    for item in rows[:7]:
        action = _humanize_token(item.get("action"))
        entity = _humanize_token(item.get("entity"))
        actor = str(item.get("actor_name") or "System")
        role = _humanize_token(item.get("actor_role"))
        key = str(item.get("entity_key") or "No key")
        created_at = _format_date(item.get("created_at"))
        items.append(
            f"""
            <article class="dashboard-audit-row">
                <div class="dashboard-audit-row__mark"></div>
                <div class="dashboard-audit-row__copy">
                    <strong title="{escape(action)}">{escape(action)}</strong>
                    <span title="{escape(entity)}">{escape(entity)} / {escape(key)}</span>
                </div>
                <div class="dashboard-audit-row__actor">
                    <span title="{escape(actor)}">{escape(actor)}</span>
                    <small>{escape(role)} / {escape(created_at)}</small>
                </div>
            </article>
            """
        )
    return f'<div class="dashboard-audit-stream">{"".join(items)}</div>'


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
    chart_height = 284
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
    chart_html: str = "",
    pills: list[str] | None = None,
    empty_message: str = "No chart data available yet.",
) -> None:
    with st.container(key=key):
        st.html(_panel_header_html(title, meta, eyebrow=eyebrow, pills=pills))
        if frame.empty or (spec is None and not chart_html):
            st.info(empty_message)
        elif chart_html:
            st.html(chart_html)
        else:
            st.vega_lite_chart(spec, width="stretch")


def _render_html_panel(
    *,
    key: str,
    title: str,
    meta: str,
    eyebrow: str,
    body_html: str,
    pills: list[str] | None = None,
) -> None:
    with st.container(key=key):
        st.html(_panel_header_html(title, meta, eyebrow=eyebrow, pills=pills))
        st.html(body_html)


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

    overview_left, overview_right = st.columns(2, gap="large")
    with overview_left:
        _render_chart_panel(
            key="dashboard_panel_project_load",
            title="Project load",
            meta="Active assignments by project.",
            eyebrow="Projects",
            frame=project_load_mix,
            spec=None,
            chart_html=_build_bar_chart_html(project_load_mix, accent_color="#6aa8ff"),
            pills=[
                f"{_format_compact_number(metrics.get('current_assignments'))} active assignments",
                f"{len(project_load_mix):,} live project bands",
            ],
            empty_message="Project deployment load will appear after assignments are created.",
        )
    with overview_right:
        _render_chart_panel(
            key="dashboard_panel_surveyor_coverage",
            title="Surveyor coverage",
            meta="Surveyors by province.",
            eyebrow="Surveyors",
            frame=surveyor_province_mix,
            spec=None,
            chart_html=_build_bar_chart_html(surveyor_province_mix, accent_color="#87f1e3"),
            pills=[
                f"{_format_compact_number(metrics.get('total_surveyors'))} surveyors",
                f"{len(surveyor_province_mix):,} province bands",
            ],
            empty_message="Surveyor coverage will appear after surveyors are added.",
        )

    portfolio_left, portfolio_right = st.columns(2, gap="large")
    with portfolio_left:
        _render_chart_panel(
            key="dashboard_panel_client_mix",
            title="Client concentration",
            meta="Projects by client.",
            eyebrow="Portfolio",
            frame=client_mix,
            spec=None,
            chart_html=_build_bar_chart_html(client_mix, accent_color="#79dcff"),
            pills=[f"{_format_compact_number(metrics.get('total_projects'))} total projects"],
            empty_message="Client concentration will appear after projects are registered.",
        )
    with portfolio_right:
        _render_chart_panel(
            key="dashboard_panel_project_status",
            title="Project lifecycle",
            meta="Projects by status.",
            eyebrow="Status",
            frame=project_status_mix,
            spec=None,
            chart_html=_build_bar_chart_html(project_status_mix, accent_color="#5fb3ff"),
            pills=[f"{_format_compact_number(metrics.get('active_projects'))} active projects"],
            empty_message="Project lifecycle data will appear after projects are created.",
        )

    project_table_col, surveyor_table_col = st.columns(2, gap="large")
    with project_table_col:
        _render_html_panel(
            key="dashboard_panel_recent_projects",
            title="Recent projects",
            meta="Compact project stream.",
            eyebrow="Projects",
            body_html=_build_project_stream_html(recent_projects),
            pills=[f"{len(recent_projects):,} latest records"],
        )
    with surveyor_table_col:
        _render_html_panel(
            key="dashboard_panel_recent_surveyors",
            title="Recent surveyors",
            meta="Readiness and payout link.",
            eyebrow="Surveyors",
            body_html=_build_surveyor_stream_html(recent_surveyors),
            pills=[f"{len(recent_surveyors):,} latest records"],
        )

    if full_view:
        governance_left, governance_right = st.columns(2, gap="large")
        with governance_left:
            _render_chart_panel(
                key="dashboard_panel_audit_flow",
                title="Audit activity timeline",
                meta="Last 14 days.",
                eyebrow="Audit",
                frame=audit_trend,
                spec=None,
                chart_html=_build_trend_chart_html(audit_trend),
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
                        "Governance signals",
                        "Approvals, payouts, and workload.",
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
                title="Access mix",
                meta="Users by role.",
                eyebrow="Users",
                frame=user_role_mix,
                spec=None,
                chart_html=_build_bar_chart_html(user_role_mix, accent_color="#79dcff"),
                pills=[f"{_format_compact_number(metrics.get('total_users'))} users"],
                empty_message="User role distribution will appear after accounts are created.",
            )
        with payout_col:
            _render_chart_panel(
                key="dashboard_panel_payouts",
                title="Payout mix",
                meta="Bank vs mobile routing.",
                eyebrow="Payout",
                frame=payment_type_mix,
                spec=None,
                chart_html=_build_bar_chart_html(payment_type_mix, accent_color="#87f1e3"),
                pills=[f"{_format_compact_number(metrics.get('total_bank_accounts'))} payout channels"],
                empty_message="Payout mix will appear after payout accounts are registered.",
            )
        with spotlight_col:
            with st.container(key="dashboard_panel_spotlight"):
                st.html(
                    _panel_header_html(
                        "Activity spotlight",
                        "Top actions, entities, and actors.",
                        eyebrow="Spotlight",
                        pills=[
                            f"{len(action_mix):,} top actions",
                            f"{len(entity_mix):,} top entities",
                        ],
                    )
                )
                st.html(_build_spotlight_html(action_mix, entity_mix, audit_rows))

        _render_html_panel(
            key="dashboard_panel_recent_activity",
            title="Recent audit",
            meta="Latest system events.",
            eyebrow="Audit",
            body_html=_build_audit_stream_html(audit_rows),
            pills=[f"{len(audit_rows):,} latest events"],
        )
