from __future__ import annotations

import base64
from datetime import date
from functools import lru_cache
from html import escape
import time
from typing import Any, Callable
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from app.core.permissions import ensure_role
from app.core.session import get_current_user
from app.design.components.cards import render_hero
from app.design.theme import LOGO_FILE
from app.services.bank_account_service import BankAccountService
from app.services.project_service import ProjectService
from app.services.surveyor_service import SurveyorService

SEARCH_QUERY_KEY = "search_reports_query"
SELECTED_PROFILE_KEY = "search_reports_selected_profile_id"
LAST_SEARCH_SIGNATURE_KEY = "search_reports_last_signature"
MATCH_CACHE_KEY = "search_reports_match_cache"
PROFILE_CACHE_KEY = "search_reports_profile_cache"
ACCOUNT_CACHE_KEY = "search_reports_account_cache"
PROJECT_CACHE_KEY = "search_reports_project_cache"
SESSION_CACHE_TTL_SECONDS = 300
CARD_PREVIEW_HEIGHT = 370
REPORT_SELECT_KEY = "search_reports_selected_report"
REPORT_PREVIEW_ACTIVE_KEY = "search_reports_preview_active"
REPORT_PREVIEW_HEIGHT = 860


def _normalize_digits(value: str | None) -> str:
    return "".join(character for character in (value or "") if character.isdigit())


def _display(value: Any, fallback: str = "Not available") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or fallback
    return str(value)


def _slugify(value: str, fallback: str = "surveyor") -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "_" for character in value.strip())
    normalized = "_".join(part for part in cleaned.split("_") if part)
    return normalized or fallback


def _payment_type_label(value: str | None) -> str:
    mapping = {
        "BANK_ACCOUNT": "Bank account",
        "MOBILE_CREDIT": "Mobile money",
    }
    return mapping.get((value or "").upper(), _display(value, "Not set"))


def _status_label(value: Any) -> str:
    return _display(value, "Not set").replace("_", " ").title()


def _boolean_badge(flag: bool) -> str:
    return "Ready" if flag else "Missing"


def _profile_initials(name: str | None) -> str:
    chunks = [part[0] for part in _display(name, "").split() if part]
    if not chunks:
        return "SR"
    return "".join(chunks[:2]).upper()


def _format_contact_line(profile: dict[str, Any]) -> str:
    primary = _display(profile.get("phone_number"), "")
    secondary = _display(profile.get("whatsapp_number"), "")
    parts = [value for value in [primary, secondary] if value]
    return " / ".join(parts) if parts else "No contact number"


def _placeholder_photo_data_uri(gender: str | None, initials: str) -> str:
    is_female = (gender or "").strip().lower().startswith("f")
    accent_start = "#7dd3fc" if is_female else "#93c5fd"
    accent_end = "#5eead4" if is_female else "#67e8f9"
    badge_label = "Profile preview" if not gender else _display(gender)
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 520">
        <defs>
            <linearGradient id="orb" x1="0" x2="1" y1="0" y2="1">
                <stop offset="0%" stop-color="{accent_start}"/>
                <stop offset="100%" stop-color="{accent_end}"/>
            </linearGradient>
        </defs>
        <circle cx="210" cy="192" r="88" fill="url(#orb)" opacity="0.32"/>
        <circle cx="210" cy="192" r="72" fill="rgba(255,255,255,0.08)"/>
        <text x="210" y="208" text-anchor="middle" fill="#f8fbff" font-size="54" font-weight="700" font-family="Segoe UI, Arial">{escape(initials)}</text>
        <text x="210" y="372" text-anchor="middle" fill="rgba(236,245,255,0.88)" font-size="24" font-weight="700" font-family="Segoe UI, Arial">{escape(badge_label)}</text>
        <text x="210" y="408" text-anchor="middle" fill="rgba(198,218,237,0.7)" font-size="16" font-weight="600" font-family="Segoe UI, Arial">Surveyor identity card</text>
        {"<circle cx='346' cy='84' r='8' fill='rgba(125, 211, 252, 0.9)'/>" if is_female else "<circle cx='346' cy='84' r='8' fill='rgba(103, 232, 249, 0.9)'/>"}
    </svg>
    """
    return f"data:image/svg+xml;charset=utf-8,{quote(svg)}"


def _profile_photo_src(profile: dict[str, Any] | None) -> str:
    if not profile:
        return _placeholder_photo_data_uri(None, "SR")
    raw_image = profile.get("tazkira_image")
    image_mime = _display(profile.get("tazkira_image_mime"), "")
    if raw_image and image_mime.startswith("image/"):
        encoded = base64.b64encode(raw_image).decode("ascii")
        return f"data:{image_mime};base64,{encoded}"
    return _placeholder_photo_data_uri(profile.get("gender"), _profile_initials(profile.get("surveyor_name")))


@lru_cache(maxsize=1)
def _ppc_logo_src() -> str:
    if not LOGO_FILE.exists():
        return ""
    encoded = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _sync_selected_profile(results: list[dict[str, Any]], signature: str) -> int | None:
    selected_id = st.session_state.get(SELECTED_PROFILE_KEY)
    result_ids = {item["surveyor_id"] for item in results}

    if st.session_state.get(LAST_SEARCH_SIGNATURE_KEY) != signature:
        st.session_state[LAST_SEARCH_SIGNATURE_KEY] = signature
        st.session_state[SELECTED_PROFILE_KEY] = results[0]["surveyor_id"] if results else None
        return st.session_state.get(SELECTED_PROFILE_KEY)

    if selected_id not in result_ids:
        st.session_state[SELECTED_PROFILE_KEY] = results[0]["surveyor_id"] if results else None

    return st.session_state.get(SELECTED_PROFILE_KEY)


def _cache_get_or_set(cache_key: str, item_key: Any, resolver: Callable[[], Any]) -> Any:
    cache = st.session_state.setdefault(cache_key, {})
    entry = cache.get(item_key)
    now = time.time()
    if isinstance(entry, dict) and "stored_at" in entry and now - float(entry["stored_at"]) <= SESSION_CACHE_TTL_SECONDS:
        return entry["value"]
    value = resolver()
    cache[item_key] = {"value": value, "stored_at": now}
    if len(cache) > 32:
        oldest = next(iter(cache))
        cache.pop(oldest, None)
    return value


def _build_result_card_html(profile: dict[str, Any], *, selected: bool = False) -> str:
    card_class = "sr-result-card is-selected" if selected else "sr-result-card"
    return f"""
    <div class="{card_class}">
        <div class="sr-result-card__row">
            <div>
                <div class="sr-result-card__title">{escape(_display(profile.get("surveyor_name")))}</div>
                <div class="sr-result-card__meta">
                    {escape(_display(profile.get("surveyor_code")))} |
                    {escape(_display(profile.get("current_province_name")))}
                </div>
            </div>
            <div class="sr-result-card__pill">{escape(str(profile.get("account_count", 0)))} accounts</div>
        </div>
        <div class="sr-result-card__chips">
            <span>{escape(_display(profile.get("phone_number"), "No phone"))}</span>
            <span>{escape(_display(profile.get("tazkira_no"), "No tazkira"))}</span>
            <span>{escape(str(profile.get("document_count", 0)))} docs</span>
        </div>
    </div>
    """


def _build_search_summary_html(mode_label: str, search_term: str, result_count: int, *, showing_recent: bool) -> str:
    descriptor = "Recent profiles" if showing_recent else "Live ranked matches"
    prompt = "Browsing the latest registered surveyors." if showing_recent else f'Search term: "{search_term}"'
    return f"""
    <div class="sr-summary-bar">
        <div class="sr-summary-bar__text">
            <span>{escape(descriptor)}</span>
            <strong>{escape(mode_label)}</strong>
        </div>
        <div class="sr-summary-bar__count">{escape(str(result_count))} results</div>
        <div class="sr-summary-bar__hint">{escape(prompt)}</div>
    </div>
    """


def _build_empty_state_html(title: str, description: str) -> str:
    return f"""
    <div class="sr-empty-state">
        <div class="sr-empty-state__orb"></div>
        <div class="sr-empty-state__kicker">Search Deck</div>
        <h3>{escape(title)}</h3>
        <p>{escape(description)}</p>
    </div>
    """


def _build_id_card_html(profile: dict[str, Any]) -> str:
    return f"""
    <div class="sr-id-card">
        <div class="sr-id-card__mesh"></div>
        <div class="sr-id-card__header">
            <div>
                <div class="sr-id-card__eyebrow">Surveyor Identity</div>
                <h3>{escape(_display(profile.get("surveyor_name")))}</h3>
                <p>{escape(_display(profile.get("surveyor_code")))} | {escape(_display(profile.get("gender")))}</p>
            </div>
            <div class="sr-id-card__status">{escape(_boolean_badge(bool(profile.get("account_count"))))} payout</div>
        </div>
        <div class="sr-id-card__body">
            <div class="sr-id-card__avatar">{escape(_profile_initials(profile.get("surveyor_name")))}</div>
            <div class="sr-id-card__grid">
                <div>
                    <span>Father name</span>
                    <strong>{escape(_display(profile.get("father_name")))}</strong>
                </div>
                <div>
                    <span>Tazkira</span>
                    <strong>{escape(_display(profile.get("tazkira_no")))}</strong>
                </div>
                <div>
                    <span>Phone</span>
                    <strong>{escape(_display(profile.get("phone_number")))}</strong>
                </div>
                <div>
                    <span>WhatsApp</span>
                    <strong>{escape(_display(profile.get("whatsapp_number")))}</strong>
                </div>
                <div>
                    <span>Email</span>
                    <strong>{escape(_display(profile.get("email_address")))}</strong>
                </div>
                <div>
                    <span>Current province</span>
                    <strong>{escape(_display(profile.get("current_province_name")))}</strong>
                </div>
            </div>
        </div>
        <div class="sr-id-card__footer">
            <span>{escape(_display(profile.get("permanent_province_name")))} permanent</span>
            <span>{escape(str(profile.get("document_count", 0)))} / 4 documents</span>
            <span>{escape(_display(profile.get("default_bank_name"), "No default bank"))}</span>
        </div>
    </div>
    """


def _build_profile_snapshot_html(profile: dict[str, Any]) -> str:
    return f"""
    <div class="sr-detail-panel">
        <div class="sr-detail-panel__header">
            <span>Profile Snapshot</span>
            <strong>{escape(_display(profile.get("surveyor_code")))}</strong>
        </div>
        <div class="sr-detail-panel__grid">
            <div>
                <label>Contact line</label>
                <strong>{escape(_format_contact_line(profile))}</strong>
            </div>
            <div>
                <label>Permanent province</label>
                <strong>{escape(_display(profile.get("permanent_province_name")))}</strong>
            </div>
            <div>
                <label>Default bank</label>
                <strong>{escape(_display(profile.get("default_bank_name"), "Not set"))}</strong>
            </div>
            <div>
                <label>Payment type</label>
                <strong>{escape(_payment_type_label(profile.get("default_payment_type")))}</strong>
            </div>
            <div>
                <label>Default payout</label>
                <strong>{escape(_display(profile.get("default_payout_value"), "Not set"))}</strong>
            </div>
            <div>
                <label>Bank network</label>
                <strong>{escape(_display(profile.get("bank_names"), "No bank linked"))}</strong>
            </div>
        </div>
    </div>
    """


def _build_document_panel_html(profile: dict[str, Any]) -> str:
    items = [
        ("CV file", bool(profile.get("has_cv_file")), _display(profile.get("cv_file_name"), "No file")),
        ("Tazkira image", bool(profile.get("has_tazkira_image")), _display(profile.get("tazkira_image_name"), "No file")),
        ("Tazkira PDF", bool(profile.get("has_tazkira_pdf")), _display(profile.get("tazkira_pdf_name"), "No file")),
        ("Tazkira Word", bool(profile.get("has_tazkira_word")), _display(profile.get("tazkira_word_name"), "No file")),
    ]
    cards = "".join(
        f"""
        <div class="sr-doc-card {'is-ready' if flag else 'is-missing'}">
            <span>{escape(label)}</span>
            <strong>{escape(_boolean_badge(flag))}</strong>
            <small>{escape(filename)}</small>
        </div>
        """
        for label, flag, filename in items
    )
    return f"""
    <div class="sr-doc-panel">
        <div class="sr-doc-panel__header">
            <span>Document Readiness</span>
            <strong>{escape(str(profile.get("document_count", 0)))} / 4</strong>
        </div>
        <div class="sr-doc-panel__grid">{cards}</div>
    </div>
    """


def _build_report_shell(title: str, subtitle: str, body_html: str, badges: list[str]) -> str:
    badge_markup = "".join(f"<span>{escape(item)}</span>" for item in badges if item)
    if not badge_markup:
        badge_markup = "<span>Controlled record</span>"
    issue_date = date.today().isoformat()
    report_id = f"{_slugify(title, 'report').upper()}-{date.today().strftime('%Y%m%d')}"
    return f"""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{escape(title)}</title>
        <style>
            :root {{
                color-scheme: light;
                --ink: #111827;
                --ink-soft: #4b5563;
                --line: #d1d5db;
                --line-strong: #9ca3af;
                --accent: #0f766e;
                --accent-strong: #134e4a;
                --accent-soft: #d9f4ef;
                --signal: #92400e;
                --signal-soft: #fff7ed;
                --danger: #991b1b;
                --danger-soft: #fee2e2;
                --surface: #ffffff;
                --surface-soft: #f8fafc;
                --surface-quiet: #f3f4f6;
                --sheet-width: 980px;
                --sheet-padding: 34px;
                --sheet-radius: 8px;
                --title-size: 31px;
                --subtitle-size: 15px;
                --section-title-size: 19px;
                --body-size: 14px;
                --label-size: 12px;
                --badge-size: 13px;
                --strong-size: 16px;
                --meta-size: 24px;
                --toolbar-size: 14px;
                --footer-size: 13px;
                --card-padding: 14px 16px;
                --grid-columns: repeat(2, minmax(0, 1fr));
            }}
            * {{
                box-sizing: border-box;
                letter-spacing: 0;
            }}
            body {{
                margin: 0;
                font-family: "Segoe UI", Arial, sans-serif;
                background: #e5e7eb;
                color: var(--ink);
            }}
            .toolbar {{
                position: sticky;
                top: 0;
                z-index: 5;
                display: flex;
                justify-content: flex-end;
                padding: 16px 20px;
                background: rgba(226, 232, 240, 0.92);
                backdrop-filter: blur(8px);
            }}
            .toolbar button {{
                border: 0;
                border-radius: 8px;
                padding: 12px 18px;
                background: var(--accent);
                color: #fff;
                font-size: var(--toolbar-size);
                font-weight: 700;
                cursor: pointer;
            }}
            .toolbar button:hover {{
                background: var(--accent-strong);
            }}
            .sheet {{
                width: min(var(--sheet-width), calc(100% - 32px));
                margin: 24px auto 40px;
                padding: var(--sheet-padding);
                border-radius: var(--sheet-radius);
                background: var(--surface);
                border: 1px solid var(--line-strong);
                box-shadow: 0 18px 40px rgba(15, 23, 42, 0.12);
            }}
            .document-ribbon {{
                display: grid;
                grid-template-columns: minmax(0, 1fr) auto;
                gap: 12px;
                align-items: center;
                margin: calc(var(--sheet-padding) * -1) calc(var(--sheet-padding) * -1) 24px;
                padding: 13px var(--sheet-padding);
                border-radius: 8px 8px 0 0;
                background: #111827;
                color: #ffffff;
                font-size: var(--label-size);
                font-weight: 800;
                text-transform: uppercase;
            }}
            .document-ribbon span {{
                color: #d1d5db;
                font-weight: 700;
                text-align: right;
            }}
            .masthead {{
                display: grid;
                grid-template-columns: 1fr auto;
                gap: 18px;
                align-items: start;
                padding-bottom: 20px;
                border-bottom: 1px solid var(--line);
            }}
            .eyebrow {{
                margin: 0 0 8px;
                color: var(--accent);
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 0;
                text-transform: uppercase;
            }}
            h1 {{
                margin: 0;
                font-size: var(--title-size);
                line-height: 1.06;
            }}
            .subtitle {{
                margin: 12px 0 0;
                color: var(--ink-soft);
                font-size: var(--subtitle-size);
                line-height: 1.65;
            }}
            .meta-box {{
                min-width: 180px;
                padding: 14px 16px;
                border-radius: 8px;
                background: var(--surface-quiet);
                border: 1px solid var(--line);
            }}
            .meta-box span {{
                display: block;
                color: var(--ink-soft);
                font-size: var(--label-size);
                text-transform: uppercase;
            }}
            .meta-box strong {{
                display: block;
                margin-top: 10px;
                font-size: var(--meta-size);
            }}
            .badges {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin: 18px 0 0;
            }}
            .badges span {{
                padding: 8px 12px;
                border-radius: 8px;
                background: var(--accent-soft);
                color: var(--accent-strong);
                font-size: var(--badge-size);
                font-weight: 700;
            }}
            .standard-strip {{
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 10px;
                margin-top: 18px;
            }}
            .standard-strip div {{
                padding: 10px 12px;
                border: 1px solid var(--line);
                border-radius: 8px;
                background: var(--surface-soft);
            }}
            .standard-strip span {{
                display: block;
                color: var(--ink-soft);
                font-size: var(--label-size);
                text-transform: uppercase;
            }}
            .standard-strip strong {{
                display: block;
                margin-top: 6px;
                font-size: var(--body-size);
            }}
            .executive-note {{
                margin-top: 18px;
                padding: 14px 16px;
                border-left: 4px solid var(--accent);
                border-radius: 8px;
                background: var(--surface-soft);
                color: var(--ink-soft);
                font-size: var(--body-size);
                line-height: 1.7;
            }}
            .section {{
                margin-top: 22px;
                break-inside: avoid;
            }}
            .section h2 {{
                margin: 0 0 14px;
                font-size: var(--section-title-size);
            }}
            .section p {{
                margin: 0 0 12px;
                color: var(--ink-soft);
                font-size: var(--body-size);
                line-height: 1.72;
            }}
            .data-grid {{
                display: grid;
                grid-template-columns: var(--grid-columns);
                gap: 12px;
                margin-top: 16px;
            }}
            .data-card {{
                padding: var(--card-padding);
                border: 1px solid var(--line);
                border-radius: 8px;
                background: var(--surface-soft);
            }}
            .data-card span,
            .doc-table td span {{
                display: block;
                color: var(--ink-soft);
                font-size: var(--label-size);
                text-transform: uppercase;
            }}
            .data-card strong {{
                display: block;
                margin-top: 8px;
                font-size: var(--strong-size);
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 12px;
                border: 1px solid var(--line);
                border-radius: 8px;
                overflow: hidden;
            }}
            th, td {{
                padding: 12px 14px;
                border-bottom: 1px solid var(--line);
                text-align: left;
                vertical-align: top;
                font-size: var(--body-size);
            }}
            th {{
                background: var(--accent-soft);
                color: var(--accent-strong);
                font-size: var(--label-size);
                text-transform: uppercase;
            }}
            thead {{
                display: table-header-group;
            }}
            tr {{
                break-inside: avoid;
            }}
            .status-pill {{
                display: inline-block;
                padding: 6px 8px;
                border-radius: 8px;
                background: var(--accent-soft);
                color: var(--accent-strong);
                font-size: var(--label-size);
                font-weight: 800;
                text-transform: uppercase;
            }}
            .status-pill.is-current {{
                background: var(--signal-soft);
                color: var(--signal);
            }}
            .status-pill.is-missing {{
                background: var(--danger-soft);
                color: var(--danger);
            }}
            .status-pill.is-neutral {{
                background: var(--surface-quiet);
                color: var(--ink-soft);
            }}
            .control-list {{
                display: grid;
                gap: 10px;
                margin-top: 14px;
                padding: 0;
                list-style: none;
            }}
            .control-list li {{
                padding: 12px 14px;
                border: 1px solid var(--line);
                border-radius: 8px;
                background: var(--surface-soft);
                color: var(--ink-soft);
                font-size: var(--body-size);
                line-height: 1.65;
            }}
            .control-list strong {{
                color: var(--ink);
            }}
            .timeline-list {{
                display: grid;
                gap: 10px;
                margin-top: 14px;
            }}
            .timeline-item {{
                display: grid;
                grid-template-columns: 130px minmax(0, 1fr) auto;
                gap: 12px;
                align-items: start;
                padding: 13px 14px;
                border: 1px solid var(--line);
                border-radius: 8px;
                background: var(--surface-soft);
            }}
            .timeline-item span {{
                color: var(--ink-soft);
                font-size: var(--label-size);
                font-weight: 800;
                text-transform: uppercase;
            }}
            .timeline-item strong {{
                display: block;
                font-size: var(--strong-size);
            }}
            .timeline-item small {{
                display: block;
                margin-top: 5px;
                color: var(--ink-soft);
                font-size: var(--footer-size);
                line-height: 1.45;
            }}
            tr:last-child td {{
                border-bottom: 0;
            }}
            .footer-note {{
                margin-top: 24px;
                padding-top: 16px;
                border-top: 1px dashed var(--line);
                color: var(--ink-soft);
                font-size: var(--footer-size);
            }}
            .signature-grid {{
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 12px;
                margin-top: 26px;
                padding-top: 18px;
                border-top: 1px solid var(--line);
            }}
            .signature-box {{
                min-height: 118px;
                padding: 14px;
                border: 1px solid var(--line);
                border-radius: 8px;
                background: var(--surface);
            }}
            .signature-box span {{
                display: block;
                color: var(--ink-soft);
                font-size: var(--label-size);
                font-weight: 800;
                text-transform: uppercase;
            }}
            .signature-box strong {{
                display: block;
                margin-top: 10px;
                font-size: var(--strong-size);
            }}
            .signature-line {{
                margin-top: 34px;
                border-top: 1px solid var(--line-strong);
                padding-top: 8px;
                color: var(--ink-soft);
                font-size: var(--footer-size);
            }}
            .page-footer {{
                display: grid;
                grid-template-columns: minmax(0, 1fr) auto;
                gap: 12px;
                margin-top: 20px;
                padding-top: 14px;
                border-top: 1px solid var(--line);
                color: var(--ink-soft);
                font-size: var(--footer-size);
                line-height: 1.55;
            }}
            @page {{
                size: A4;
                margin: 12mm;
            }}
            @media print {{
                body {{
                    background: #fff;
                }}
                .toolbar {{
                    display: none;
                }}
                .sheet {{
                    width: 100%;
                    margin: 0;
                    padding: 0;
                    border-radius: 0;
                    border: 0;
                    box-shadow: none;
                }}
                .document-ribbon {{
                    margin: 0 0 18px;
                    border-radius: 0;
                    print-color-adjust: exact;
                    -webkit-print-color-adjust: exact;
                }}
            }}
            @media (min-width: 768px) and (max-width: 1023.98px) {{
                :root {{
                    --sheet-width: 860px;
                    --sheet-padding: 24px;
                    --sheet-radius: 8px;
                    --title-size: 28px;
                    --subtitle-size: 14px;
                    --section-title-size: 18px;
                    --body-size: 13px;
                    --label-size: 11px;
                    --badge-size: 12px;
                    --strong-size: 15px;
                    --meta-size: 22px;
                    --toolbar-size: 13px;
                    --footer-size: 12px;
                    --card-padding: 13px 14px;
                }}
            }}
            @media (max-width: 767.98px) {{
                :root {{
                    --sheet-width: 100%;
                    --sheet-padding: 18px;
                    --sheet-radius: 8px;
                    --title-size: 24px;
                    --subtitle-size: 13px;
                    --section-title-size: 16px;
                    --body-size: 12px;
                    --label-size: 10px;
                    --badge-size: 11px;
                    --strong-size: 14px;
                    --meta-size: 20px;
                    --toolbar-size: 12px;
                    --footer-size: 11px;
                    --card-padding: 12px 13px;
                    --grid-columns: 1fr;
                }}
                .sheet {{
                    width: calc(100% - 18px);
                }}
                .masthead,
                .data-grid,
                .standard-strip,
                .timeline-item,
                .signature-grid,
                .page-footer {{
                    grid-template-columns: 1fr;
                }}
                .document-ribbon {{
                    grid-template-columns: 1fr;
                }}
                .document-ribbon span {{
                    text-align: left;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="toolbar">
            <button type="button" onclick="window.print()">Print report</button>
        </div>
        <main class="sheet">
            <div class="document-ribbon">
                <strong>Internal Official Record</strong>
                <span>Survey Management Control File</span>
            </div>
            <section class="masthead">
                <div>
                    <p class="eyebrow">Search and Reports</p>
                    <h1>{escape(title)}</h1>
                    <p class="subtitle">{escape(subtitle)}</p>
                    <div class="badges">{badge_markup}</div>
                    <div class="standard-strip">
                        <div><span>Control number</span><strong>{escape(report_id)}</strong></div>
                        <div><span>Source</span><strong>Survey Management Database</strong></div>
                        <div><span>Classification</span><strong>Internal official record</strong></div>
                        <div><span>Format</span><strong>A4 print-ready HTML</strong></div>
                    </div>
                    <div class="executive-note">
                        This report is prepared from live administrative records for controlled internal review.
                        It should be validated against the system before external circulation or final approval.
                    </div>
                </div>
                <div class="meta-box">
                    <span>Issue date</span>
                    <strong>{escape(issue_date)}</strong>
                </div>
            </section>
            {body_html}
            <section class="signature-grid" aria-label="Approval and verification">
                <div class="signature-box">
                    <span>Prepared by</span>
                    <strong>Operations Office</strong>
                    <div class="signature-line">Name, signature, and date</div>
                </div>
                <div class="signature-box">
                    <span>Reviewed by</span>
                    <strong>Administration</strong>
                    <div class="signature-line">Name, signature, and date</div>
                </div>
                <div class="signature-box">
                    <span>Approved by</span>
                    <strong>Authorized Manager</strong>
                    <div class="signature-line">Name, signature, and date</div>
                </div>
            </section>
            <footer class="page-footer">
                <span>Generated from the Search and Reports workspace. Unauthorized edits invalidate this document.</span>
                <strong>{escape(report_id)}</strong>
            </footer>
        </main>
    </body>
    </html>
    """


@st.cache_data(ttl=300, show_spinner=False)
def _build_hr_letter(profile: dict[str, Any], actor: dict[str, Any] | None) -> str:
    issuer = _display(actor.get("full_name") if actor else None, "System Office")
    role = _display(actor.get("role") if actor else None, "Operations")
    body_html = f"""
    <section class="section">
        <h2>Administrative Control Summary</h2>
        <div class="data-grid">
            <div class="data-card"><span>Subject</span><strong>{escape(_display(profile.get("surveyor_name")))}</strong></div>
            <div class="data-card"><span>Surveyor code</span><strong>{escape(_display(profile.get("surveyor_code")))}</strong></div>
            <div class="data-card"><span>Current province</span><strong>{escape(_display(profile.get("current_province_name")))}</strong></div>
            <div class="data-card"><span>Verification scope</span><strong>HR and administrative review</strong></div>
        </div>
    </section>
    <section class="section">
        <h2>Verification Statement</h2>
        <p>
            This official internal letter confirms that
            <strong>{escape(_display(profile.get("surveyor_name")))}</strong>
            is registered in the survey management system under surveyor code
            <strong>{escape(_display(profile.get("surveyor_code")))}</strong>. The record is available
            for HR, onboarding, operations, and controlled administrative verification.
        </p>
        <div class="data-grid">
            <div class="data-card"><span>Father name</span><strong>{escape(_display(profile.get("father_name")))}</strong></div>
            <div class="data-card"><span>Tazkira number</span><strong>{escape(_display(profile.get("tazkira_no")))}</strong></div>
            <div class="data-card"><span>Current province</span><strong>{escape(_display(profile.get("current_province_name")))}</strong></div>
            <div class="data-card"><span>Contact line</span><strong>{escape(_format_contact_line(profile))}</strong></div>
        </div>
    </section>
    <section class="section">
        <h2>Issuing Controls</h2>
        <p>
            This document is issued for internal administrative use only. Any downstream approval,
            contracting action, or field deployment decision remains subject to the organization's
            operational policy and the latest approved personnel record.
        </p>
        <div class="data-grid">
            <div class="data-card"><span>Prepared by</span><strong>{escape(issuer)}</strong></div>
            <div class="data-card"><span>Role</span><strong>{escape(role)}</strong></div>
        </div>
        <ul class="control-list">
            <li><strong>Record basis:</strong> identity, contact, location, and system registration fields available at the time of issue.</li>
            <li><strong>Use limitation:</strong> this letter does not replace signed contracts, finance clearance, or management approval.</li>
        </ul>
        <div class="footer-note">Generated directly from the Search and Reports workspace with official control metadata.</div>
    </section>
    """
    return _build_report_shell(
        "HR Letter",
        "A print-ready verification letter for HR and administrative review.",
        body_html,
        [
            _display(profile.get("surveyor_code")),
            _display(profile.get("surveyor_name")),
            _display(profile.get("current_province_name")),
        ],
    )


@st.cache_data(ttl=300, show_spinner=False)
def _build_bank_account_report(profile: dict[str, Any], accounts: list[dict[str, Any]]) -> str:
    active_count = sum(1 for item in accounts if item.get("is_active"))
    default_accounts = [item for item in accounts if item.get("is_default")]
    default_account = default_accounts[0] if default_accounts else {}
    bank_channels = sum(1 for item in accounts if item.get("payment_type") == "BANK_ACCOUNT")
    mobile_channels = sum(1 for item in accounts if item.get("payment_type") == "MOBILE_CREDIT")
    if accounts:
        rows = "".join(
            f"""
            <tr>
                <td>{escape(_display(item.get("bank_name")))}</td>
                <td>{escape(_payment_type_label(item.get("payment_type")))}</td>
                <td>{escape(_display(item.get("account_title"), "Not set"))}</td>
                <td>{escape(_display(item.get("account_number") or item.get("mobile_number"), "Not set"))}</td>
                <td><span class="status-pill {'is-current' if item.get('is_default') else 'is-neutral'}">{escape("Default" if item.get("is_default") else "Secondary")}</span></td>
                <td><span class="status-pill {'is-neutral' if not item.get('is_active') else ''}">{escape("Active" if item.get("is_active") else "Inactive")}</span></td>
            </tr>
            """
            for item in accounts
        )
        table_html = f"""
        <table>
            <thead>
                <tr>
                    <th>Bank</th>
                    <th>Payment type</th>
                    <th>Account title</th>
                    <th>Payout number</th>
                    <th>Priority</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        """
    else:
        table_html = "<p>No bank account is registered for this surveyor yet.</p>"

    body_html = f"""
    <section class="section">
        <h2>Payment Channel Summary</h2>
        <p>
            This official finance report lists all payment channels linked to
            <strong>{escape(_display(profile.get("surveyor_name")))}</strong>.
            The summary is intended for payout validation, default-channel review, and administrative reconciliation.
        </p>
        <div class="data-grid">
            <div class="data-card"><span>Total channels</span><strong>{escape(str(len(accounts)))}</strong></div>
            <div class="data-card"><span>Active channels</span><strong>{escape(str(active_count))}</strong></div>
            <div class="data-card"><span>Bank account channels</span><strong>{escape(str(bank_channels))}</strong></div>
            <div class="data-card"><span>Mobile money channels</span><strong>{escape(str(mobile_channels))}</strong></div>
            <div class="data-card"><span>Default bank</span><strong>{escape(_display(default_account.get("bank_name") or profile.get("default_bank_name"), "Not set"))}</strong></div>
            <div class="data-card"><span>Default payout number</span><strong>{escape(_display(default_account.get("account_number") or default_account.get("mobile_number") or profile.get("default_payout_value"), "Not set"))}</strong></div>
        </div>
        <ul class="control-list">
            <li><strong>Finance control:</strong> default accounts should be verified before bulk payout preparation or payroll export.</li>
            <li><strong>Operational control:</strong> inactive channels are retained for historical reference and should not be used for new payments.</li>
        </ul>
        {table_html}
        <div class="footer-note">Use this sheet when finance or administration needs a printable payout overview.</div>
    </section>
    """
    return _build_report_shell(
        "Bank Account Report",
        "A printable payout-channel report for finance and administration.",
        body_html,
        [
            _display(profile.get("surveyor_code")),
            f"{len(accounts)} channels",
            _display(profile.get("default_bank_name"), "No default bank"),
        ],
    )


@st.cache_data(ttl=300, show_spinner=False)
def _build_profile_report(profile: dict[str, Any], accounts: list[dict[str, Any]]) -> str:
    document_count = int(profile.get("document_count") or 0)
    active_account_count = int(profile.get("active_account_count") or sum(1 for item in accounts if item.get("is_active")))
    contact_status = "Ready" if profile.get("phone_number") and profile.get("whatsapp_number") else "Review needed"
    dossier_status = "Complete" if document_count >= 4 and active_account_count >= 1 else "Review needed"
    body_html = f"""
    <section class="section">
        <h2>Dossier Control Summary</h2>
        <p>
            This profile dossier consolidates identity, contact, location, document, and payout readiness
            for formal operations and administration review.
        </p>
        <div class="data-grid">
            <div class="data-card"><span>Dossier status</span><strong>{escape(dossier_status)}</strong></div>
            <div class="data-card"><span>Contact status</span><strong>{escape(contact_status)}</strong></div>
            <div class="data-card"><span>Documents ready</span><strong>{escape(str(document_count))} / 4</strong></div>
            <div class="data-card"><span>Active payout channels</span><strong>{escape(str(active_account_count))}</strong></div>
        </div>
    </section>
    <section class="section">
        <h2>Surveyor Profile</h2>
        <div class="data-grid">
            <div class="data-card"><span>Surveyor code</span><strong>{escape(_display(profile.get("surveyor_code")))}</strong></div>
            <div class="data-card"><span>Surveyor name</span><strong>{escape(_display(profile.get("surveyor_name")))}</strong></div>
            <div class="data-card"><span>Gender</span><strong>{escape(_display(profile.get("gender")))}</strong></div>
            <div class="data-card"><span>Father name</span><strong>{escape(_display(profile.get("father_name")))}</strong></div>
            <div class="data-card"><span>Tazkira</span><strong>{escape(_display(profile.get("tazkira_no")))}</strong></div>
            <div class="data-card"><span>Email</span><strong>{escape(_display(profile.get("email_address")))}</strong></div>
            <div class="data-card"><span>Phone</span><strong>{escape(_display(profile.get("phone_number")))}</strong></div>
            <div class="data-card"><span>WhatsApp</span><strong>{escape(_display(profile.get("whatsapp_number")))}</strong></div>
            <div class="data-card"><span>Permanent province</span><strong>{escape(_display(profile.get("permanent_province_name")))}</strong></div>
            <div class="data-card"><span>Current province</span><strong>{escape(_display(profile.get("current_province_name")))}</strong></div>
            <div class="data-card"><span>Documents ready</span><strong>{escape(str(document_count))} / 4</strong></div>
            <div class="data-card"><span>Linked payout channels</span><strong>{escape(str(len(accounts)))}</strong></div>
        </div>
        <ul class="control-list">
            <li><strong>Administrative use:</strong> confirm identity fields before issuing HR letters, assignments, or contract paperwork.</li>
            <li><strong>Field use:</strong> confirm current province and contact fields before dispatch, interview scheduling, or project reassignment.</li>
        </ul>
        <div class="footer-note">This one-page sheet combines identity, contact, location, and payout readiness.</div>
    </section>
    """
    return _build_report_shell(
        "Profile Summary",
        "A concise printable profile for field, operations, and admin use.",
        body_html,
        [
            _display(profile.get("surveyor_code")),
            _display(profile.get("surveyor_name")),
            f"{profile.get('document_count', 0)} docs ready",
        ],
    )


@st.cache_data(ttl=300, show_spinner=False)
def _build_document_checklist(profile: dict[str, Any]) -> str:
    rows = [
        ("CV file", bool(profile.get("has_cv_file")), _display(profile.get("cv_file_name"), "No file")),
        ("Tazkira image", bool(profile.get("has_tazkira_image")), _display(profile.get("tazkira_image_name"), "No file")),
        ("Tazkira PDF", bool(profile.get("has_tazkira_pdf")), _display(profile.get("tazkira_pdf_name"), "No file")),
        ("Tazkira Word", bool(profile.get("has_tazkira_word")), _display(profile.get("tazkira_word_name"), "No file")),
    ]
    ready_count = sum(1 for _, status, _ in rows if status)
    missing_count = len(rows) - ready_count
    readiness_status = "Complete" if missing_count == 0 else "Action required"
    row_markup = "".join(
        f"""
        <tr>
            <td>{escape(label)}</td>
            <td><span class="status-pill {'is-missing' if not status else ''}">{escape("Ready" if status else "Missing")}</span></td>
            <td>{escape(filename)}</td>
        </tr>
        """
        for label, status, filename in rows
    )
    body_html = f"""
    <section class="section">
        <h2>Document Checklist</h2>
        <p>
            This checklist helps HR and administration confirm the document readiness of
            <strong>{escape(_display(profile.get("surveyor_name")))}</strong>.
        </p>
        <div class="data-grid">
            <div class="data-card"><span>Readiness status</span><strong>{escape(readiness_status)}</strong></div>
            <div class="data-card"><span>Ready documents</span><strong>{escape(str(ready_count))} / {escape(str(len(rows)))}</strong></div>
            <div class="data-card"><span>Missing documents</span><strong>{escape(str(missing_count))}</strong></div>
            <div class="data-card"><span>Surveyor code</span><strong>{escape(_display(profile.get("surveyor_code")))}</strong></div>
        </div>
        <table class="doc-table">
            <thead>
                <tr>
                    <th>Document</th>
                    <th>Status</th>
                    <th>Stored file</th>
                </tr>
            </thead>
            <tbody>{row_markup}</tbody>
        </table>
        <ul class="control-list">
            <li><strong>Completion control:</strong> all four document slots should be ready before final onboarding or contract packaging.</li>
            <li><strong>File control:</strong> stored file names should match the latest verified personnel documents in the system.</li>
        </ul>
        <div class="footer-note">Use this report before onboarding, contract packaging, or compliance review.</div>
    </section>
    """
    return _build_report_shell(
        "Document Checklist",
        "A print-friendly document completeness report.",
        body_html,
        [
            _display(profile.get("surveyor_code")),
            _display(profile.get("surveyor_name")),
            f"{profile.get('document_count', 0)} of 4 ready",
        ],
    )


@st.cache_data(ttl=300, show_spinner=False)
def _build_project_assignment_report(profile: dict[str, Any], assignments: list[dict[str, Any]]) -> str:
    current_assignments = [item for item in assignments if item.get("is_current_active")]
    total_assignments = len(assignments)
    active_names = ", ".join(_display(item.get("project_name")) for item in current_assignments) or "No current active project"
    active_status = "Active assignment on file" if current_assignments else "No active assignment on file"
    province_names = sorted(
        {
            _display(item.get("work_province_name"), _display(item.get("work_province_code"), "Not set"))
            for item in assignments
        }
    )
    province_scope = ", ".join(province_names[:6]) if province_names else "No province scope registered"
    if len(province_names) > 6:
        province_scope = f"{province_scope}, +{len(province_names) - 6} more"

    if assignments:
        rows = "".join(
            f"""
            <tr>
                <td>{escape(_display(item.get("project_code")))}</td>
                <td>{escape(_display(item.get("project_name")))}</td>
                <td>{escape(_display(item.get("client_name"), "No client"))}</td>
                <td>{escape(_status_label(item.get("project_status")))}</td>
                <td>{escape(_status_label(item.get("assignment_status")))}</td>
                <td>{escape(_display(item.get("role"), "Surveyor"))}</td>
                <td>{escape(_display(item.get("work_province_name"), _display(item.get("work_province_code"), "Not set")))}</td>
                <td>{escape(_display(item.get("assignment_start_date")))}</td>
                <td>{escape(_display(item.get("assignment_end_date"), "Open"))}</td>
                <td><span class="status-pill {'is-current' if item.get('is_current_active') else ''}">{escape("Current" if item.get("is_current_active") else "History")}</span></td>
            </tr>
            """
            for item in assignments
        )
        table_html = f"""
        <table>
            <thead>
                <tr>
                    <th>Project code</th>
                    <th>Project</th>
                    <th>Client</th>
                    <th>Project status</th>
                    <th>Assignment status</th>
                    <th>Role</th>
                    <th>Province</th>
                    <th>Start</th>
                    <th>End</th>
                    <th>Track</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        """
        timeline_items = "".join(
            f"""
            <div class="timeline-item">
                <span>{escape(_display(item.get("assignment_start_date")))}</span>
                <div>
                    <strong>{escape(_display(item.get("project_name")))}</strong>
                    <small>
                        {escape(_display(item.get("project_code")))} |
                        {escape(_display(item.get("client_name"), "No client"))} |
                        {escape(_display(item.get("work_province_name"), "No province"))} |
                        {escape(_status_label(item.get("assignment_status")))} assignment
                    </small>
                </div>
                <div><span class="status-pill {'is-current' if item.get('is_current_active') else ''}">{escape("Current" if item.get("is_current_active") else _status_label(item.get("project_status")))}</span></div>
            </div>
            """
            for item in assignments[:10]
        )
        timeline_html = f"""
        <section class="section">
            <h2>Assignment Timeline</h2>
            <p>
                The timeline below keeps the latest ten assignments visible for quick operational review.
            </p>
            <div class="timeline-list">{timeline_items}</div>
        </section>
        """
    else:
        table_html = "<p>No project assignment has been registered for this surveyor yet.</p>"
        timeline_html = ""

    body_html = f"""
    <section class="section">
        <h2>Project Assignment Overview</h2>
        <p>
            This official operations report shows which projects
            <strong>{escape(_display(profile.get("surveyor_name")))}</strong>
            has worked on and which project is currently active. It is intended for assignment review,
            field planning, workload traceability, and administrative verification.
        </p>
        <div class="data-grid">
            <div class="data-card"><span>Total assignments</span><strong>{escape(str(total_assignments))}</strong></div>
            <div class="data-card"><span>Current active projects</span><strong>{escape(str(len(current_assignments)))}</strong></div>
            <div class="data-card"><span>Current assignment status</span><strong>{escape(active_status)}</strong></div>
            <div class="data-card"><span>Active project name</span><strong>{escape(active_names)}</strong></div>
            <div class="data-card"><span>Surveyor code</span><strong>{escape(_display(profile.get("surveyor_code")))}</strong></div>
            <div class="data-card"><span>Province scope</span><strong>{escape(province_scope)}</strong></div>
        </div>
        <ul class="control-list">
            <li><strong>Current assignment rule:</strong> a project is marked current only when the project is active, the assignment is active, and the date window includes today.</li>
            <li><strong>Operations control:</strong> closed, inactive, or historical assignments remain visible for traceability and should not be treated as current workload.</li>
        </ul>
        {table_html}
        <div class="footer-note">Current means the project status is ACTIVE, the assignment status is ACTIVE, and today's date is inside the assignment date window.</div>
    </section>
    {timeline_html}
    """
    return _build_report_shell(
        "Project Work History",
        "A project participation and current-assignment report for operations review.",
        body_html,
        [
            _display(profile.get("surveyor_code")),
            f"{total_assignments} assignments",
            f"{len(current_assignments)} current",
        ],
    )


def _report_file_name(label: str, profile: dict[str, Any]) -> str:
    return f"{_slugify(label)}_{_slugify(_display(profile.get('surveyor_code'), 'surveyor'))}.html"


def _report_payloads(
    profile: dict[str, Any],
    accounts: list[dict[str, Any]],
    project_assignments: list[dict[str, Any]],
    actor: dict[str, Any] | None,
) -> dict[str, Callable[[], dict[str, str]]]:
    return {
        "HR Letter": lambda: {
            "html": _build_hr_letter(profile, actor),
            "file_name": _report_file_name("hr_letter", profile),
        },
        "Bank Report": lambda: {
            "html": _build_bank_account_report(profile, accounts),
            "file_name": _report_file_name("bank_report", profile),
        },
        "Profile Summary": lambda: {
            "html": _build_profile_report(profile, accounts),
            "file_name": _report_file_name("profile_summary", profile),
        },
        "Document Checklist": lambda: {
            "html": _build_document_checklist(profile),
            "file_name": _report_file_name("document_checklist", profile),
        },
        "Project Work History": lambda: {
            "html": _build_project_assignment_report(profile, project_assignments),
            "file_name": _report_file_name("project_work_history", profile),
        },
    }


def _build_profile_info_section_html(title: str, rows: list[tuple[str, Any, str]]) -> str:
    row_markup = "".join(
        f"""
        <div class="sr-profile-line">
            <span>{escape(label)}</span>
            <strong>{escape(_display(value, fallback))}</strong>
        </div>
        """
        for label, value, fallback in rows
    )
    return f"""
    <section class="sr-profile-section">
        <h4>{escape(title)}</h4>
        <div class="sr-profile-lines">{row_markup}</div>
    </section>
    """


def _build_profile_accounts_html(accounts: list[dict[str, Any]]) -> str:
    if not accounts:
        return """
        <section class="sr-profile-section">
            <h4>Payout channels</h4>
            <div class="sr-profile-lines">
                <div class="sr-profile-line">
                    <span>Registered accounts</span>
                    <strong>No bank account linked</strong>
                </div>
            </div>
        </section>
        """

    rows = "".join(
        f"""
        <div class="sr-profile-line sr-profile-line--wide">
            <span>{escape(_display(item.get("bank_name")))}</span>
            <strong>
                {escape(_payment_type_label(item.get("payment_type")))} |
                {escape(_display(item.get("account_title"), "No account title"))} |
                {escape(_display(item.get("account_number") or item.get("mobile_number"), "No payout number"))} |
                {escape("Default" if item.get("is_default") else "Secondary")} |
                {escape("Active" if item.get("is_active") else "Inactive")}
            </strong>
        </div>
        """
        for item in accounts
    )
    return f"""
    <section class="sr-profile-section">
        <h4>Payout channels</h4>
        <div class="sr-profile-lines">{rows}</div>
    </section>
    """


def _build_profile_projects_html(assignments: list[dict[str, Any]]) -> str:
    if not assignments:
        return """
        <section class="sr-profile-section">
            <h4>Project history</h4>
            <div class="sr-profile-lines">
                <div class="sr-profile-line">
                    <span>Assignments</span>
                    <strong>No project assignment linked</strong>
                </div>
            </div>
        </section>
        """

    current = [item for item in assignments if item.get("is_current_active")]
    rows = "".join(
        f"""
        <div class="sr-profile-line sr-profile-line--wide">
            <span>{escape(_display(item.get("project_code")))}</span>
            <strong>
                {escape(_display(item.get("project_name")))} |
                {escape(_status_label(item.get("project_status")))} project |
                {escape(_status_label(item.get("assignment_status")))} assignment |
                {escape("Current" if item.get("is_current_active") else "History")}
            </strong>
        </div>
        """
        for item in assignments[:5]
    )
    return f"""
    <section class="sr-profile-section">
        <h4>Project history</h4>
        <div class="sr-profile-lines">
            <div class="sr-profile-line">
                <span>Total assignments</span>
                <strong>{escape(str(len(assignments)))} total | {escape(str(len(current)))} current active</strong>
            </div>
            {rows}
        </div>
    </section>
    """


def _build_match_snapshot_html(
    profile: dict[str, Any],
    match_count: int,
    accounts: list[dict[str, Any]] | None = None,
    project_assignments: list[dict[str, Any]] | None = None,
) -> str:
    account_list = accounts or []
    assignment_list = project_assignments or []
    info_sections = "".join(
        [
            _build_profile_info_section_html(
                "Identity",
                [
                    ("Surveyor code", profile.get("surveyor_code"), "Not available"),
                    ("Surveyor name", profile.get("surveyor_name"), "Not available"),
                    ("Father name", profile.get("father_name"), "Not available"),
                    ("Gender", profile.get("gender"), "Not available"),
                    ("Tazkira", profile.get("tazkira_no"), "Not available"),
                ],
            ),
            _build_profile_info_section_html(
                "Contact",
                [
                    ("Phone", profile.get("phone_number"), "No phone number"),
                    ("WhatsApp", profile.get("whatsapp_number"), "No WhatsApp number"),
                    ("Email", profile.get("email_address"), "No email address"),
                ],
            ),
            _build_profile_info_section_html(
                "Location",
                [
                    ("Current province", profile.get("current_province_name"), "Not available"),
                    ("Current code", profile.get("current_province_code"), "Not available"),
                    ("Permanent province", profile.get("permanent_province_name"), "Not available"),
                    ("Permanent code", profile.get("permanent_province_code"), "Not available"),
                ],
            ),
            _build_profile_info_section_html(
                "Documents",
                [
                    ("Documents ready", f"{profile.get('document_count', 0)} / 4", "0 / 4"),
                    (
                        "CV file",
                        f"{_boolean_badge(bool(profile.get('has_cv_file')))} | {_display(profile.get('cv_file_name'), 'No file')}",
                        "Missing | No file",
                    ),
                    (
                        "Tazkira image",
                        f"{_boolean_badge(bool(profile.get('has_tazkira_image')))} | {_display(profile.get('tazkira_image_name'), 'No file')}",
                        "Missing | No file",
                    ),
                    (
                        "Tazkira PDF",
                        f"{_boolean_badge(bool(profile.get('has_tazkira_pdf')))} | {_display(profile.get('tazkira_pdf_name'), 'No file')}",
                        "Missing | No file",
                    ),
                    (
                        "Tazkira Word",
                        f"{_boolean_badge(bool(profile.get('has_tazkira_word')))} | {_display(profile.get('tazkira_word_name'), 'No file')}",
                        "Missing | No file",
                    ),
                ],
            ),
            _build_profile_info_section_html(
                "Default payout",
                [
                    ("Linked channels", profile.get("account_count"), "0"),
                    ("Active channels", profile.get("active_account_count"), "0"),
                    ("Default bank", profile.get("default_bank_name"), "Not set"),
                    ("Payment type", _payment_type_label(profile.get("default_payment_type")), "Not set"),
                    ("Default payout", profile.get("default_payout_value"), "Not set"),
                    ("Bank network", profile.get("bank_names"), "No bank linked"),
                ],
            ),
            _build_profile_accounts_html(account_list),
            _build_profile_projects_html(assignment_list),
        ]
    )
    return f"""
    <div class="sr-match-shell">
        <div class="sr-match-shell__head">
            <div>
                <div class="sr-match-shell__kicker">Complete surveyor dossier</div>
                <h3>{escape(_display(profile.get("surveyor_name")))}</h3>
                <p>
                    {escape(_display(profile.get("surveyor_code")))} | {escape(_display(profile.get("current_province_name")))} |
                    {escape(str(match_count))} match{'es' if match_count != 1 else ''}
                </p>
            </div>
            <div class="sr-match-shell__seal">Verified</div>
        </div>
        <div class="sr-profile-dossier">{info_sections}</div>
    </div>
    """


@st.cache_data(ttl=300, show_spinner=False)
def _build_flip_card_component(profile: dict[str, Any] | None, accounts: list[dict[str, Any]]) -> str:
    photo_src = _profile_photo_src(profile)
    ppc_logo = _ppc_logo_src()
    ppc_logo_markup = (
        f'<img class="ppc-logo" src="{ppc_logo}" alt="PPC">'
        if ppc_logo
        else '<div class="ppc-wordmark">PPC</div>'
    )

    if profile is None:
        surveyor_name = "Surveyor name"
        surveyor_code = "PPC-SEARCH"
        province = "Current province"
        permanent_province = "Permanent province"
        gender = "Preview"
        father_name = "Father name"
        tazkira_no = "Not selected"
        phone_number = "No number"
        whatsapp_number = "No WhatsApp"
        email_address = "No email"
        bank_name = "No bank linked"
        payout_value = "Not available"
        document_text = "Documents pending"
        account_text = "No payout channels yet"
        issue_badge = "Live preview"
        accent_note = "Type ID, name, code, number, or tazkira"
    else:
        surveyor_name = _display(profile.get("surveyor_name"))
        surveyor_code = _display(profile.get("surveyor_code"))
        province = _display(profile.get("current_province_name"))
        permanent_province = _display(profile.get("permanent_province_name"))
        gender = _display(profile.get("gender"))
        father_name = _display(profile.get("father_name"))
        tazkira_no = _display(profile.get("tazkira_no"))
        phone_number = _display(profile.get("phone_number"))
        whatsapp_number = _display(profile.get("whatsapp_number"))
        email_address = _display(profile.get("email_address"))
        bank_name = _display(profile.get("default_bank_name"), "No default bank")
        payout_value = _display(profile.get("default_payout_value"), "Not set")
        document_text = f"{profile.get('document_count', 0)} / 4 documents ready"
        account_text = f"{len(accounts)} payout channel{'s' if len(accounts) != 1 else ''}"
        issue_badge = "Verified profile"
        accent_note = f"{province} | {gender}"

    card_id = f"flip-card-{_slugify(surveyor_code, 'profile')}"
    return f"""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{
                box-sizing: border-box;
                letter-spacing: 0;
            }}
            :root {{
                --card-width: min(121mm, calc(100vw - 28px));
                --card-ratio: 85.6 / 53.98;
                --card-radius: calc(var(--card-width) * 0.045);
                --card-padding: calc(var(--card-width) * 0.052);
                --eyebrow-size: clamp(7px, calc(var(--card-width) * 0.025), 10px);
                --micro-size: clamp(7px, calc(var(--card-width) * 0.027), 10px);
                --body-size: clamp(8px, calc(var(--card-width) * 0.030), 12px);
                --label-size: clamp(6.8px, calc(var(--card-width) * 0.024), 9px);
                --value-size: clamp(8px, calc(var(--card-width) * 0.030), 11.5px);
                --code-size: clamp(13px, calc(var(--card-width) * 0.044), 18px);
                --name-size: clamp(12.5px, calc(var(--card-width) * 0.047), 20px);
            }}
            body {{
                margin: 0;
                font-family: "Segoe UI", Arial, sans-serif;
                background: transparent;
                color: #f8fbff;
                overflow: hidden;
            }}
            .wrap {{
                min-height: 100svh;
                display: grid;
                place-items: center;
                padding: 12px 8px 8px;
            }}
            .toggle {{
                position: absolute;
                opacity: 0;
                pointer-events: none;
            }}
            .scene {{
                display: block;
                width: var(--card-width);
                aspect-ratio: var(--card-ratio);
                cursor: pointer;
                perspective: 1100px;
            }}
            .card {{
                position: relative;
                width: 100%;
                height: 100%;
                transform-style: preserve-3d;
                transition: transform 420ms cubic-bezier(0.22, 1, 0.36, 1);
            }}
            .toggle:checked + .scene .card {{
                transform: rotateY(180deg);
            }}
            .face {{
                position: absolute;
                inset: 0;
                overflow: hidden;
                border-radius: var(--card-radius);
                padding: var(--card-padding);
                backface-visibility: hidden;
                box-shadow: 0 16px 34px rgba(0,0,0,0.34);
            }}
            .face::before {{
                content: "";
                position: absolute;
                inset: 0;
                pointer-events: none;
                background:
                    linear-gradient(115deg, rgba(255,255,255,0.18), transparent 24%, rgba(255,255,255,0.08) 42%, transparent 58%),
                    linear-gradient(90deg, rgba(255,255,255,0.04), transparent 46%, rgba(255,255,255,0.05));
                opacity: 0.72;
                z-index: 1;
            }}
            .face::after {{
                content: "";
                position: absolute;
                inset: 8% -10% 8% 56%;
                pointer-events: none;
                background:
                    linear-gradient(135deg,
                        transparent 0 43%,
                        rgba(255, 229, 166, 0.16) 44% 47%,
                        transparent 48% 100%) 0 0 / 26px 26px,
                    linear-gradient(45deg,
                        transparent 0 43%,
                        rgba(125, 220, 255, 0.10) 44% 47%,
                        transparent 48% 100%) 13px 0 / 26px 26px,
                    linear-gradient(90deg,
                        transparent 0%,
                        rgba(255,255,255,0.02) 34%,
                        rgba(255,255,255,0.06) 100%);
                opacity: 0.34;
                filter: blur(0.45px);
                mix-blend-mode: screen;
                -webkit-mask-image: linear-gradient(90deg, transparent 0%, rgba(0,0,0,0.18) 28%, rgba(0,0,0,0.82) 100%);
                mask-image: linear-gradient(90deg, transparent 0%, rgba(0,0,0,0.18) 28%, rgba(0,0,0,0.82) 100%);
                z-index: 0;
            }}
            .front {{
                background:
                    radial-gradient(circle at 18% 12%, rgba(125, 220, 255, 0.26), transparent 28%),
                    radial-gradient(circle at 88% 18%, rgba(109, 255, 222, 0.18), transparent 22%),
                    linear-gradient(145deg, #081725 0%, #12314a 48%, #194b6b 100%);
                border: 1px solid rgba(220, 242, 255, 0.34);
            }}
            .back {{
                transform: rotateY(180deg);
                background:
                    radial-gradient(circle at 78% 18%, rgba(247,200,115,0.16), transparent 22%),
                    radial-gradient(circle at 18% 86%, rgba(121,220,255,0.15), transparent 24%),
                    linear-gradient(145deg, #07111d 0%, #101f30 54%, #182c41 100%);
                border: 1px solid rgba(200, 232, 255, 0.22);
            }}
            .face-content {{
                position: relative;
                z-index: 2;
                height: 100%;
                display: grid;
                grid-template-rows: auto 1fr auto;
                gap: calc(var(--card-width) * 0.024);
            }}
            .back .face-content {{
                grid-template-rows: auto auto 1fr;
                gap: calc(var(--card-width) * 0.02);
            }}
            .surface-head {{
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: calc(var(--card-width) * 0.035);
            }}
            .identity {{
                color: rgba(240,248,255,0.88);
                font-size: var(--eyebrow-size);
                font-weight: 800;
                text-transform: uppercase;
                line-height: 1.1;
            }}
            .status {{
                flex: 0 0 auto;
                padding: 4px 7px;
                border-radius: 999px;
                border: 1px solid rgba(255,255,255,0.12);
                background: rgba(255,255,255,0.09);
                color: #f6fbff;
                font-size: var(--micro-size);
                font-weight: 700;
                white-space: nowrap;
            }}
            .front-body {{
                display: grid;
                grid-template-columns: 31% 1fr;
                grid-template-areas:
                    "photo info"
                    "details details";
                column-gap: calc(var(--card-width) * 0.045);
                row-gap: calc(var(--card-width) * 0.004);
                min-height: 0;
                align-items: start;
                padding-top: 0;
                padding-bottom: calc(var(--card-width) * 0.012);
            }}
            .photo {{
                width: 88%;
                height: calc(var(--card-width) * 0.32);
                object-fit: cover;
                display: block;
                grid-area: photo;
                align-self: start;
                justify-self: start;
                margin-top: calc(var(--card-width) * -0.012);
                border: 0;
                outline: 0;
                box-shadow: none;
                background: transparent;
            }}
            .info-stack {{
                grid-area: info;
                min-width: 0;
                display: flex;
                flex-direction: column;
                gap: calc(var(--card-width) * 0.006);
            }}
            .brand-row {{
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: calc(var(--card-width) * 0.025);
                margin-top: calc(var(--card-width) * -0.018);
            }}
            .ppc-logo,
            .ppc-wordmark {{
                width: calc(var(--card-width) * 0.31);
                height: calc(var(--card-width) * 0.135);
            }}
            .ppc-logo {{
                object-fit: contain;
                display: block;
            }}
            .ppc-wordmark {{
                display: grid;
                place-items: center;
                color: #f8fbff;
                font-size: var(--body-size);
                font-weight: 800;
            }}
            .surveyor-code {{
                margin: 0;
                color: #f7fbff;
                font-size: var(--code-size);
                line-height: 1.05;
                font-weight: 800;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                font-variant-numeric: tabular-nums;
            }}
            .surveyor-name {{
                color: rgba(232,243,255,0.95);
                font-size: var(--name-size);
                line-height: 1.04;
                min-width: 0;
                font-weight: 700;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .surveyor-sub {{
                color: rgba(225,239,252,0.88);
                font-size: var(--body-size);
                line-height: 1.22;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .quick-grid {{
                grid-area: details;
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                grid-template-rows: repeat(2, auto);
                grid-auto-flow: column;
                row-gap: calc(var(--card-width) * 0.006);
                column-gap: calc(var(--card-width) * 0.04);
                align-self: start;
                padding-top: 0;
                margin-top: calc(var(--card-width) * -0.035);
            }}
            .info-line {{
                min-width: 0;
                display: grid;
                grid-template-columns: auto minmax(0, 1fr);
                align-items: baseline;
                gap: 5px;
            }}
            .info-line span {{
                color: rgba(222,238,252,0.82);
                font-size: var(--label-size);
                font-weight: 700;
                text-transform: uppercase;
                white-space: nowrap;
            }}
            .info-line span::after {{
                content: ":";
            }}
            .info-line strong {{
                color: #f4f9ff;
                font-size: var(--value-size);
                line-height: 1.18;
                font-weight: 700;
                text-align: left;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .surface-foot {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 6px;
                padding-top: calc(var(--card-width) * 0.02);
                border-top: 1px solid rgba(255,255,255,0.1);
            }}
            .foot-text {{
                flex: 1 1 0;
                min-width: 0;
                color: rgba(233,244,255,0.88);
                font-size: var(--micro-size);
                font-weight: 700;
                text-align: center;
                white-space: nowrap;
                text-overflow: ellipsis;
                overflow: hidden;
            }}
            .stripe {{
                width: calc(100% + (var(--card-padding) * 2));
                height: calc(var(--card-width) * 0.105);
                margin: 0 calc(var(--card-padding) * -1);
                background:
                    linear-gradient(90deg, #020304 0%, #0a0b0d 22%, #14171f 50%, #090b0f 78%, #020304 100%);
            }}
            .back-body {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                column-gap: calc(var(--card-width) * 0.045);
                row-gap: calc(var(--card-width) * 0.014);
                align-content: center;
                min-height: 0;
                padding-top: calc(var(--card-width) * 0.008);
            }}
            .detail-line {{
                min-width: 0;
                display: grid;
                grid-template-columns: minmax(42px, auto) minmax(0, 1fr);
                align-items: start;
                gap: 6px;
                padding-bottom: calc(var(--card-width) * 0.006);
                border-bottom: 1px solid rgba(211, 235, 255, 0.09);
            }}
            .detail-line span {{
                color: rgba(222,238,252,0.78);
                font-size: var(--label-size);
                font-weight: 700;
                text-transform: uppercase;
                white-space: nowrap;
            }}
            .detail-line span::after {{
                content: ":";
            }}
            .detail-line strong {{
                color: #f7fbff;
                font-size: var(--value-size);
                line-height: 1.22;
                font-weight: 700;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .hint {{
                margin-top: 8px;
                text-align: center;
                color: rgba(224,239,255,0.7);
                font-size: var(--micro-size);
                font-weight: 700;
                text-transform: uppercase;
            }}

            @media (max-width: 520px) {{
                :root {{
                    --card-width: min(430px, calc(100vw - 14px));
                    --card-padding: calc(var(--card-width) * 0.045);
                    --eyebrow-size: clamp(6.2px, calc(var(--card-width) * 0.021), 8.4px);
                    --micro-size: clamp(6.2px, calc(var(--card-width) * 0.022), 8.6px);
                    --body-size: clamp(7.2px, calc(var(--card-width) * 0.026), 10.2px);
                    --label-size: clamp(6px, calc(var(--card-width) * 0.020), 7.8px);
                    --value-size: clamp(7.2px, calc(var(--card-width) * 0.025), 9.8px);
                    --code-size: clamp(11.5px, calc(var(--card-width) * 0.038), 15.5px);
                    --name-size: clamp(11px, calc(var(--card-width) * 0.040), 16px);
                }}

                .wrap {{
                    align-content: start;
                    padding: 6px 4px 4px;
                }}

                .face {{
                    box-shadow: 0 10px 24px rgba(0,0,0,0.30);
                }}

                .face-content {{
                    gap: calc(var(--card-width) * 0.016);
                }}

                .back .face-content {{
                    gap: calc(var(--card-width) * 0.014);
                }}

                .surface-head {{
                    gap: calc(var(--card-width) * 0.02);
                }}

                .status {{
                    padding: 3px 5px;
                }}

                .front-body {{
                    grid-template-columns: 29% 1fr;
                    column-gap: calc(var(--card-width) * 0.034);
                    row-gap: calc(var(--card-width) * 0.006);
                    padding-bottom: 0;
                }}

                .photo {{
                    width: 92%;
                    height: calc(var(--card-width) * 0.255);
                    margin-top: 0;
                }}

                .brand-row {{
                    margin-top: 0;
                }}

                .ppc-logo,
                .ppc-wordmark {{
                    width: calc(var(--card-width) * 0.25);
                    height: calc(var(--card-width) * 0.095);
                }}

                .info-stack {{
                    gap: calc(var(--card-width) * 0.008);
                }}

                .surveyor-name,
                .surveyor-sub,
                .surveyor-code,
                .info-line strong,
                .detail-line strong,
                .foot-text {{
                    min-width: 0;
                }}

                .quick-grid {{
                    row-gap: calc(var(--card-width) * 0.004);
                    column-gap: calc(var(--card-width) * 0.028);
                    margin-top: 0;
                }}

                .info-line {{
                    grid-template-columns: minmax(34px, auto) minmax(0, 1fr);
                    gap: 3px;
                }}

                .surface-foot {{
                    gap: 4px;
                    padding-top: calc(var(--card-width) * 0.014);
                }}

                .stripe {{
                    height: calc(var(--card-width) * 0.086);
                }}

                .back-body {{
                    column-gap: calc(var(--card-width) * 0.026);
                    row-gap: calc(var(--card-width) * 0.006);
                    align-content: start;
                }}

                .detail-line {{
                    grid-template-columns: minmax(39px, auto) minmax(0, 1fr);
                    gap: 4px;
                    padding-bottom: calc(var(--card-width) * 0.004);
                }}

                .hint {{
                    margin-top: 6px;
                }}
            }}

            @media (max-width: 340px) {{
                :root {{
                    --card-width: calc(100vw - 12px);
                }}

                .face-content {{
                    gap: 4px;
                }}

                .front-body {{
                    grid-template-columns: 28% 1fr;
                    column-gap: 8px;
                }}

                .photo {{
                    height: calc(var(--card-width) * 0.235);
                }}

                .quick-grid {{
                    column-gap: 7px;
                }}

                .status {{
                    max-width: 34%;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <input class="toggle" id="{escape(card_id)}" type="checkbox">
            <label class="scene" for="{escape(card_id)}">
                <article class="card">
                    <section class="face front">
                        <div class="face-content">
                            <div class="surface-head">
                                <div>
                                    <div class="identity">Surveyor identity card</div>
                                    <div class="surveyor-code">{escape(surveyor_code)}</div>
                                </div>
                                <div class="status">{escape(issue_badge)}</div>
                            </div>
                            <div class="front-body">
                                <img class="photo" src="{photo_src}" alt="Profile photo">
                                <div class="info-stack">
                                    <div class="brand-row">
                                        {ppc_logo_markup}
                                    </div>
                                    <div>
                                        <div class="surveyor-name">{escape(surveyor_name)}</div>
                                        <div class="surveyor-sub">Father: {escape(father_name)}</div>
                                        <div class="surveyor-sub">{escape(accent_note)}</div>
                                    </div>
                                </div>
                                <div class="quick-grid">
                                    <div class="info-line"><span>Gender</span><strong>{escape(gender)}</strong></div>
                                    <div class="info-line"><span>Current</span><strong>{escape(province)}</strong></div>
                                    <div class="info-line"><span>Tazkira</span><strong>{escape(tazkira_no)}</strong></div>
                                    <div class="info-line"><span>Phone</span><strong>{escape(phone_number)}</strong></div>
                                </div>
                            </div>
                            <div class="surface-foot">
                                <div class="foot-text">{escape(document_text)}</div>
                                <div class="foot-text">{escape(account_text)}</div>
                            </div>
                        </div>
                    </section>
                    <section class="face back">
                        <div class="face-content">
                            <div class="surface-head">
                                <div>
                                    <div class="identity">Verified profile details</div>
                                    <div class="surveyor-code">{escape(surveyor_code)}</div>
                                </div>
                                <div class="status">Secure format</div>
                            </div>
                            <div class="stripe" aria-hidden="true"></div>
                            <div class="back-body">
                                <div class="detail-line"><span>Surveyor</span><strong>{escape(surveyor_name)}</strong></div>
                                <div class="detail-line"><span>Father</span><strong>{escape(father_name)}</strong></div>
                                <div class="detail-line"><span>Permanent</span><strong>{escape(permanent_province)}</strong></div>
                                <div class="detail-line"><span>Current</span><strong>{escape(province)}</strong></div>
                                <div class="detail-line"><span>WhatsApp</span><strong>{escape(whatsapp_number)}</strong></div>
                                <div class="detail-line"><span>Email</span><strong>{escape(email_address)}</strong></div>
                                <div class="detail-line"><span>Bank</span><strong>{escape(bank_name)}</strong></div>
                                <div class="detail-line"><span>Payout</span><strong>{escape(payout_value)}</strong></div>
                            </div>
                        </div>
                    </section>
                </article>
            </label>
            <div class="hint">Click the card to flip it</div>
        </div>
    </body>
    </html>
    """

def _render_report_actions(
    profile: dict[str, Any],
    accounts: list[dict[str, Any]],
    project_assignments: list[dict[str, Any]],
    actor: dict[str, Any] | None,
) -> None:
    payloads = _report_payloads(profile, accounts, project_assignments, actor)
    labels = list(payloads.keys())

    st.caption("Report options")
    selected_report = st.selectbox(
        "Select report",
        labels,
        key=REPORT_SELECT_KEY,
        label_visibility="collapsed",
    )
    selected_payload = payloads[selected_report]()

    view_col, download_col = st.columns(2, gap="small")
    with view_col:
        if st.button(
            "View selected report",
            key=f"view_report_{profile.get('surveyor_id')}",
            width="stretch",
            type="secondary",
        ):
            st.session_state[REPORT_PREVIEW_ACTIVE_KEY] = True
    with download_col:
        st.download_button(
            "Download selected report",
            data=selected_payload["html"],
            file_name=selected_payload["file_name"],
            mime="text/html",
            key=f"download_selected_report_{profile.get('surveyor_id')}",
            type="primary",
            width="stretch",
        )

    if st.session_state.get(REPORT_PREVIEW_ACTIVE_KEY):
        st.caption(f"Preview: {selected_report}")
        components.html(
            selected_payload["html"],
            height=REPORT_PREVIEW_HEIGHT,
            scrolling=True,
        )


def render_search_reports_page() -> None:
    ensure_role("super_admin", "admin", "manager")
    surveyor_service = SurveyorService()
    bank_account_service = BankAccountService()
    project_service = ProjectService()
    actor = get_current_user()

    render_hero("Search & Reports", kicker=None)

    search_col, card_col = st.columns([0.9, 1.1], gap="large")

    with search_col:
        search_term = st.text_input(
            "Search surveyor",
            key=SEARCH_QUERY_KEY,
            placeholder="Search by ID, surveyor code, name, number, or tazkira",
            label_visibility="collapsed",
        ).strip()

    matches: list[dict[str, Any]] = []
    selected_profile: dict[str, Any] | None = None
    accounts: list[dict[str, Any]] = []
    project_assignments: list[dict[str, Any]] = []
    selected_id: int | None = None
    query_ready = len(search_term) >= 2

    if search_term and query_ready:
        signature = search_term.casefold()
        matches = _cache_get_or_set(
            MATCH_CACHE_KEY,
            ("smart", signature, 8),
            lambda: surveyor_service.search_profiles(search_term, search_by="SMART", limit=8),
        )
        selected_id = _sync_selected_profile(matches, search_term.casefold())
        if selected_id:
            selected_profile = _cache_get_or_set(
                PROFILE_CACHE_KEY,
                selected_id,
                lambda: surveyor_service.get_profile_detail(selected_id),
            )
            if selected_profile:
                accounts = _cache_get_or_set(
                    ACCOUNT_CACHE_KEY,
                    selected_profile["surveyor_id"],
                    lambda: bank_account_service.list_surveyor_accounts(selected_profile["surveyor_id"]),
                )
                project_assignments = _cache_get_or_set(
                    PROJECT_CACHE_KEY,
                    selected_profile["surveyor_id"],
                    lambda: project_service.list_assignments_for_surveyor(selected_profile["surveyor_id"]),
                )
    elif search_term:
        st.session_state[LAST_SEARCH_SIGNATURE_KEY] = None
        st.session_state[SELECTED_PROFILE_KEY] = None
        st.session_state[REPORT_PREVIEW_ACTIVE_KEY] = False
    else:
        st.session_state[LAST_SEARCH_SIGNATURE_KEY] = None
        st.session_state[SELECTED_PROFILE_KEY] = None
        st.session_state[REPORT_PREVIEW_ACTIVE_KEY] = False

    with search_col:
        if selected_profile:
            st.html(
                _build_match_snapshot_html(
                    selected_profile,
                    len(matches),
                    accounts,
                    project_assignments,
                )
            )
        elif search_term and not query_ready:
            st.html(
                _build_empty_state_html(
                    "Type at least 2 characters.",
                    "Add one more letter or digit and the smart search engine will return a ranked surveyor result instantly.",
                )
            )
        elif search_term:
            st.html(
                _build_empty_state_html(
                    "No surveyor found.",
                    "Type a cleaner ID, exact name, surveyor code, number, or tazkira to get an instant match.",
                )
            )
        else:
            st.html(
                _build_empty_state_html(
                    "Start with one smart search.",
                    "As soon as you type an ID, name, code, number, or tazkira, the best surveyor match will appear on the card.",
                )
            )

    with card_col:
        st.html('<div class="sr-card-align-spacer" aria-hidden="true"></div>')
        components.html(
            _build_flip_card_component(selected_profile, accounts),
            height=CARD_PREVIEW_HEIGHT,
            scrolling=False,
        )

    if selected_profile:
        _render_report_actions(selected_profile, accounts, project_assignments, actor)
    else:
        st.session_state[REPORT_PREVIEW_ACTIVE_KEY] = False
