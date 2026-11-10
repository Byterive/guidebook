"""
title: ui_helpers
purpose: Streamlit helpers for the "departure board" look: inject the stylesheet once per page, split-flap cells, status tags and count chips, status-coloured table cells, a coloured
         status dot, and a sidebar skeleton. Colours of the statuses live here and in ../tokens/design-tokens.json (keep the two equal).
inputs: ui_style.css next to this file; Streamlit theme from config.toml
outputs: Streamlit widgets and escaped HTML strings for st.html
usage: from ui_helpers import apply_style, flap, status_tag, status_chip, style_status, dot, sidebar
requires: streamlit, pandas
"""
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

STATUS_COLOR = {"PASSED": "#2F7D6D", "DOUBTFUL": "#E2A93B", "FAILED": "#B4483C", "UNKNOWN": "#4A5862", "UNTESTED": "#3F6C9A", "n/a": "#8C989E"}
STATUS_INK = {"PASSED": "#FFFFFF", "DOUBTFUL": "#18222A", "FAILED": "#FFFFFF", "UNKNOWN": "#FFFFFF", "UNTESTED": "#FFFFFF", "n/a": "#46545C"}   # text on the solid colour
STATUS_ORDER = ["PASSED", "DOUBTFUL", "UNKNOWN", "UNTESTED", "FAILED"]
BOARD_INK, BOARD_BG, AMBER = "#F2EBD3", "#18222A", "#F2B33D"
STYLE_FILE = Path(__file__).with_name("ui_style.css")


def apply_style() -> None:
    """Inject the global stylesheet. Call once at the top of every page."""
    st.html("<style>" + STYLE_FILE.read_text(encoding="utf-8") + "</style>")


def style_status(df: pd.DataFrame, cols) -> "pd.io.formats.style.Styler":
    """Paint the status words in `cols` of a table with their solid colour."""
    def paint(v):
        c = STATUS_COLOR.get(v)
        if not c:
            return ""
        if v == "n/a":
            return ""      # plain text in the theme's own colour, readable on light and dark
        return f"background-color: {c}; color: {STATUS_INK[v]}; font-weight: 600"
    return df.style.map(paint, subset=list(cols))


def flap(text, status: str | None = None, cls: str = "", delay: float = 0.0) -> str:
    """One split-flap cell. `status` paints it in that status colour; `cls` may be wide, run (amber text) or miss (grey italic); text is escaped."""
    style = f"animation-delay:{delay:.2f}s;"
    if status in STATUS_COLOR:
        style += (f"background-color:{STATUS_COLOR[status]};color:{STATUS_INK[status]};background-image:none;" if status != "n/a"
                  else "background-color:transparent;color:#C9D2D6;box-shadow:inset 0 0 0 1.5px #5F6E77;")
    return f'<span class="sg-flap {cls}" style="{style}">{escape(str(text))}</span>'


def status_chip(n: int, status: str) -> str:
    """A count in the status colour; a real zero stays visible but unpainted."""
    if n == 0:
        return '<span class="sg-chip zero">0</span>'
    if status == "n/a":
        return f'<span class="sg-chip na">{n}</span>'
    return f'<span class="sg-chip" style="background:{STATUS_COLOR[status]};color:{STATUS_INK[status]}">{n}</span>'


def status_tag(status: str) -> str:
    """The status word on its colour, as on the board's flaps."""
    if status == "n/a" or status not in STATUS_COLOR:
        return f'<span class="sg-chip na">{escape(str(status))}</span>'
    return f'<span class="sg-chip" style="background:{STATUS_COLOR[status]};color:{STATUS_INK[status]};letter-spacing:.02em">{status}</span>'


def dot(label: str, state: str) -> None:
    """A coloured dot and a label: state is ok, stale, failed or missing."""
    color = {"ok": "green", "stale": "orange", "failed": "red", "missing": "gray"}.get(state, "gray")
    st.markdown(f":{color}[●] {label}")


def sidebar(title: str, notes=()) -> None:
    """Sidebar skeleton: the stylesheet, the app name and short captions (data freshness, read-only notice, ...)."""
    apply_style()
    with st.sidebar:
        st.markdown(f"### {title}")
        for n in notes:
            st.caption(n)
