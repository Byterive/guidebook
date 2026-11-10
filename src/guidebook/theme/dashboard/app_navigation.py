"""
title: app_navigation
purpose: The navigation pattern of the look: pages as tabs in the top header; a named group becomes a drop-down menu in that header. Replace the page functions with your own.
inputs: none
outputs: a Streamlit multi-page app
usage: python -m streamlit run app_navigation.py --server.address 127.0.0.1   (start from the folder that holds .streamlit/config.toml)
requires: streamlit
"""
import streamlit as st

import page_pattern   # the sample page in this folder; replace with your own page modules

st.set_page_config(page_title="My app", page_icon=":material/monitoring:", layout="wide")

PAGES = {
    "": [st.Page(page_pattern.render, title="Overview", icon=":material/dashboard:", url_path="overview", default=True),      # "" = tabs shown directly in the header
         st.Page(page_pattern.render, title="Details", icon=":material/table_rows:", url_path="details")],
    "Reports": [st.Page(page_pattern.render, title="Daily", icon=":material/fact_check:", url_path="reports-daily"),        # a named group = one drop-down
                st.Page(page_pattern.render, title="Weekly", icon=":material/fact_check:", url_path="reports-weekly")],
}
st.navigation(PAGES, position="top").run()
