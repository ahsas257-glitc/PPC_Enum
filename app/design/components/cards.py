from html import escape
from textwrap import dedent

import streamlit as st


def _compact_html(markup: str) -> str:
    return "".join(line.strip() for line in dedent(markup).splitlines() if line.strip())


def _render_html(markup: str) -> None:
    st.html(_compact_html(markup))


def _length_bucket(value: str, *, short: int, medium: int, long: int) -> str:
    length = len((value or "").strip())
    if length <= short:
        return "short"
    if length <= medium:
        return "medium"
    if length <= long:
        return "long"
    return "xlong"


def render_hero(title: str, description: str | None = None, *, kicker: str | None = "Workspace") -> None:
    title_markup = escape(title)
    description_markup = f"<p>{escape(description)}</p>" if description else ""
    kicker_markup = (
        f"""
            <div class="glass-hero-kicker">
                <span class="glass-hero-dot"></span>
                <span>{escape(kicker)}</span>
            </div>
        """
        if kicker
        else ""
    )
    _render_html(
        f"""
        <div class="glass-hero">
            <div class="glass-hero-backdrop"></div>
            {kicker_markup}
            <div class="glass-hero-grid">
                <div>
                    <h1>{title_markup}</h1>
                    {description_markup}
                </div>
                <div class="glass-hero-orbit" aria-hidden="true">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        </div>
        """
    )


def render_showcase(features: list[tuple[str, str]]) -> None:
    cards_markup = "".join(
        (
            f'<div class="showcase-card"><div class="showcase-card-title">{escape(title)}</div>'
            f"{f'<p>{escape(description)}</p>' if description else ''}</div>"
        )
        for title, description in features
    )
    _render_html(f'<div class="showcase-grid">{cards_markup}</div>')


def render_stat_band(items: list[tuple[str, str]]) -> None:
    chip_parts: list[str] = []
    for label, value in items:
        label_text = str(label)
        value_text = str(value)
        label_bucket = _length_bucket(label_text, short=10, medium=18, long=30)
        value_bucket = _length_bucket(value_text, short=10, medium=18, long=30)
        chip_parts.append(
            (
                f'<div class="stat-band-chip stat-label-{label_bucket} stat-value-{value_bucket}">'
                f'<span title="{escape(label_text)}">{escape(label_text)}</span>'
                f'<strong title="{escape(value_text)}">{escape(value_text)}</strong>'
                f"</div>"
            )
        )
    chips_markup = "".join(chip_parts)
    _render_html(f'<div class="stat-band">{chips_markup}</div>')


def render_panel_intro(
    title: str,
    meta: str | None = None,
    *,
    eyebrow: str | None = "Workspace",
    class_name: str | None = None,
) -> None:
    meta_markup = f'<p class="glass-panel-meta">{escape(meta)}</p>' if meta else ""
    eyebrow_markup = f'<div class="panel-intro-kicker">{escape(eyebrow)}</div>' if eyebrow else ""
    panel_class = "panel-intro"
    if class_name:
        panel_class = f"{panel_class} {class_name}"
    _render_html(
        f"""
        <div class="{panel_class}">
            {eyebrow_markup}
            <div class="panel-intro-row">
                <div>
                    <h3>{escape(title)}</h3>
                    {meta_markup}
                </div>
                <div class="panel-orb"></div>
            </div>
        </div>
        """
    )


def render_auth_intro(title: str, description: str | None = None) -> None:
    render_panel_intro(title, description, eyebrow=None)
