"""
title: page_pattern
purpose: The shape of one dashboard page in this look: title, one-sentence lede, a row of metrics, a dark "board" of split-flap cells with status colours, a status-count matrix, a plain
         table with status colouring, and a caption naming the data source. Each page is a thin function; the data comes from your own code. All numbers below are sample numbers.
inputs: none (sample data)
outputs: Streamlit widgets
usage: used by app_navigation.py; copy and replace the sample rows with your data
requires: streamlit, pandas
"""
import pandas as pd
import streamlit as st

from ui_helpers import flap, sidebar, status_chip, status_tag, style_status

SAMPLE = [("Service A", "PASSED", "12 of 12"), ("Service B", "DOUBTFUL", "7 of 12"), ("Service C", "FAILED", "2 of 12"), ("Service D", "UNTESTED", "0 of 12")]


def board_html(rows, title="Status board", fresh="Sample data") -> str:
    """The dark board: one row per item, flap cells for the name, the status and the progress."""
    body = "".join(f"<tr><td>{flap(name, cls='wide')}</td><td>{flap(status, status)}</td><td>{flap(progress)}</td></tr>" for name, status, progress in rows)
    return (f'<div class="sg-board"><h2>{title}</h2><p class="fresh ok">{fresh}</p><table><thead><tr><th>Item</th><th>Status</th><th>Progress</th></tr></thead>'
            f"<tbody>{body}</tbody></table><p class=\"foot\">Colour is never the only signal: the word stays on the cell.</p></div>")


def matrix_html(counts: dict) -> str:
    """Counts per group (rows) and status (columns), each in its status colour."""
    statuses = ["PASSED", "DOUBTFUL", "UNKNOWN", "UNTESTED", "FAILED"]
    head = "".join(f"<th>{s.title()}</th>" for s in statuses)
    rows = "".join(f"<tr><td>{group}</td>" + "".join(f"<td>{status_chip(c.get(s, 0), s)}</td>" for s in statuses) + "</tr>" for group, c in counts.items())
    return f'<table class="sg-matrix"><thead><tr><th>Group</th>{head}</tr></thead><tbody>{rows}</tbody></table>'


def render() -> None:
    sidebar("My app", ["Read-only. Sample data."])
    st.title("Overview")
    st.html('<p class="sg-lede">One sentence that says what this page shows and why it matters.</p>')
    m = st.columns(4)
    m[0].metric("Items", "4")
    m[1].metric("Passed", "1")
    m[2].metric("Needs a look", "2")
    m[3].metric("Not started", "1")
    st.html(board_html(SAMPLE))
    st.subheader("By group")
    st.html(matrix_html({"Group one": {"PASSED": 3, "FAILED": 1}, "Group two": {"DOUBTFUL": 2, "UNTESTED": 4}}))
    st.subheader("Table")
    df = pd.DataFrame(SAMPLE, columns=["Item", "Status", "Progress"])
    st.dataframe(style_status(df, ["Status"]), hide_index=True, width="stretch")
    st.html("Status tags: " + " ".join(status_tag(x) for x in ("PASSED", "DOUBTFUL", "FAILED", "UNTESTED", "UNKNOWN")))
    st.caption("Source: sample list in page_pattern.py. A missing value is shown as missing, never as zero.")
