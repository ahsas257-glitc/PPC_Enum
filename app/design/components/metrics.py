from html import escape

import streamlit as st


def _length_bucket(value: str, *, short: int, medium: int, long: int) -> str:
    length = len((value or "").strip())
    if length <= short:
        return "short"
    if length <= medium:
        return "medium"
    if length <= long:
        return "long"
    return "xlong"


def render_metrics(items: list[tuple[str, int | str]], *, variant: str = "default") -> None:
    if not items:
        return
    grid_class = "glass-metric-grid glass-metric-grid--compact" if variant == "compact" else "glass-metric-grid"
    card_base_class = "glass-metric-card glass-metric-card--compact" if variant == "compact" else "glass-metric-card"
    cards_markup_parts: list[str] = []
    for label, value in items:
        label_text = str(label)
        value_text = str(value)
        label_bucket = _length_bucket(label_text, short=10, medium=18, long=30)
        value_bucket = _length_bucket(value_text, short=8, medium=14, long=22)
        cards_markup_parts.append(
            (
                f'<div class="{card_base_class} metric-label-{label_bucket} metric-value-{value_bucket}">'
                f'<div class="glass-metric-label" title="{escape(label_text)}">{escape(label_text)}</div>'
                f'<div class="glass-metric-value" title="{escape(value_text)}">{escape(value_text)}</div>'
                f"</div>"
            )
        )
    cards_markup = "".join(cards_markup_parts)
    st.html(f'<div class="{grid_class}">{cards_markup}</div>')
