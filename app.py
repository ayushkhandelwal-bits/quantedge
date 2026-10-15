"""Quantitative Trading & Derivatives Analytics Dashboard — Streamlit entry point.

Run:  streamlit run app.py
"""
import streamlit as st

import config
from src import ui

st.set_page_config(page_title=config.APP_NAME, page_icon=config.ICON_PATH, layout="wide", initial_sidebar_state="expanded")
st.logo(config.LOGO_PATH, size="large", icon_image=config.ICON_PATH)
ui.init_state()

pages = [
    st.Page("views/overview.py", title="Executive Overview", icon="🏠", default=True),
    st.Page("views/market_explorer.py", title="Market Explorer & Data", icon="🔎"),
    st.Page("views/correlation_regimes.py", title="Correlation & Regimes", icon="🔗"),
    st.Page("views/strategy_lab.py", title="Trading Strategy Lab", icon="🧪"),
    st.Page("views/pattern_validation.py", title="Pattern Validation", icon="🕯️"),
    st.Page("views/backtesting.py", title="Backtesting & Performance", icon="📊"),
    st.Page("views/risk_robustness.py", title="Risk & Robustness", icon="🛡️"),
    st.Page("views/derivatives.py", title="Derivatives Analytics", icon="⚖️"),
    st.Page("views/business_outcomes.py", title="Business Outcomes", icon="💼"),
    st.Page("views/methodology.py", title="Methodology & Guide", icon="📘"),
]
nav = st.navigation(pages)
if nav.title != "Methodology & Guide":
    ui.sidebar()
else:
    with st.sidebar:
        st.caption("Reference page. Instrument and strategy controls appear on the analysis pages.")
        ui.sidebar_author()
nav.run()
