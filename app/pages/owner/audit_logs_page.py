import pandas as pd
import streamlit as st

from app.core.permissions import ensure_role
from app.design.components.cards import render_hero, render_panel_intro
from app.design.components.filters import apply_text_filter
from app.design.components.tables import render_table
from app.services.audit_service import AuditService


def render_audit_logs_page() -> None:
    ensure_role("super_admin")
    render_hero(
        "Security",
        kicker="Audit Logs",
    )
    render_panel_intro("Recent Logs", eyebrow=None)
    rows = pd.DataFrame(AuditService().list_recent(limit=250, include_payload=False))
    if not rows.empty:
        rows = rows[["audit_id", "actor_name", "actor_role", "action", "entity", "entity_key", "created_at"]]
        rows = apply_text_filter(rows, "Search audit logs")
    render_table(rows)
