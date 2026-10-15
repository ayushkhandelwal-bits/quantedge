"""Central configuration for the Quantitative Trading & Derivatives Analytics Dashboard.

Every assumption that drives a calculation lives here so it can be changed in one place
and shown to the user in the Methodology tab.
"""
from __future__ import annotations

import os
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
SAMPLE_DIR = os.path.join(DATA_DIR, "sample")
DB_DIR = os.path.join(DATA_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "results.db")

for _d in (RAW_DIR, PROCESSED_DIR, SAMPLE_DIR, DB_DIR):
    os.makedirs(_d, exist_ok=True)

APP_NAME = "QuantEdge"
APP_TAGLINE = "Quantitative Trading & Derivatives Analytics"
APP_TITLE = "Quantitative Trading & Derivatives Analytics Dashboard"
LOGO_PATH = os.path.join(BASE_DIR, "assets", "quantedge_logo.svg")
ICON_PATH = os.path.join(BASE_DIR, "assets", "quantedge_icon.svg")

# Author details shown in the footer
AUTHOR_NAME = "Ayush Khandelwal"
AUTHOR_PROGRAMME = "MBA, Business Analytics"
AUTHOR_AFFILIATION = "BITS Pilani"
AUTHOR_EMAIL = "ayushkhandelwal.connect@gmail.com"
AUTHOR_LINKEDIN = "https://www.linkedin.com/in/ayushjhanginiya/"

# --------------------------------------------------------------------------- universe
# symbol -> (display name, description, currency, market)
INSTRUMENTS: dict[str, dict] = {
    "^NSEI": {"name": "NIFTY 50", "desc": "NSE benchmark index of 50 large Indian companies", "ccy": "INR", "market": "NSE index", "tradable": False},
    "RELIANCE.NS": {"name": "Reliance Industries", "desc": "Energy, retail and telecom conglomerate", "ccy": "INR", "market": "NSE equity", "tradable": True},
    "ITC.NS": {"name": "ITC", "desc": "FMCG, hotels, paperboards and agri-business", "ccy": "INR", "market": "NSE equity", "tradable": True},
    "HDFCBANK.NS": {"name": "HDFC Bank", "desc": "Largest Indian private-sector bank", "ccy": "INR", "market": "NSE equity", "tradable": True},
    "BHARTIARTL.NS": {"name": "Bharti Airtel", "desc": "Telecommunications services", "ccy": "INR", "market": "NSE equity", "tradable": True},
    "TCS.NS": {"name": "Tata Consultancy Services", "desc": "IT services and consulting", "ccy": "INR", "market": "NSE equity", "tradable": True},
    "INFY.NS": {"name": "Infosys", "desc": "IT services and consulting", "ccy": "INR", "market": "NSE equity", "tradable": True},
    "SBIN.NS": {"name": "State Bank of India", "desc": "Largest Indian public-sector bank", "ccy": "INR", "market": "NSE equity", "tradable": True},
    "^GSPC": {"name": "S&P 500", "desc": "US benchmark index of 500 large companies", "ccy": "USD", "market": "US index", "tradable": False},
}
DEFAULT_SYMBOL = "RELIANCE.NS"
DEFAULT_BENCHMARK = "^NSEI"

# --------------------------------------------------------------------------- dates
DEFAULT_YEARS = 5
TODAY = date.today()
DEFAULT_END = TODAY
DEFAULT_START = date(TODAY.year - DEFAULT_YEARS, TODAY.month, min(TODAY.day, 28))

# --------------------------------------------------------------------------- analytics
TRADING_DAYS = 252             # annualisation for daily data
INITIAL_CAPITAL = 1_000_000.0  # INR 10 lakh default

# Risk-free rate: USER ASSUMPTION, not a live feed.
# Default reflects the RBI policy repo rate of 5.50% announced at the October 2026 MPC
# meeting (per press reports). Verify the current figure at https://dbie.rbi.org.in/
RISK_FREE_RATE = 0.055
RISK_FREE_SOURCE = "Assumption: RBI policy repo rate 5.50% (Oct 2026 MPC, per press reports). Editable; verify at dbie.rbi.org.in"

# --------------------------------------------------------------------------- data fetching
YF_MAX_RETRIES = 3
YF_BACKOFF_SECONDS = 2.0
YF_TIMEOUT_SECONDS = 20
CACHE_MAX_AGE_HOURS = 24       # cached data older than this is flagged "stale" (still usable)

# --------------------------------------------------------------------------- data labels
SRC_LIVE = "Live download (Yahoo Finance)"
SRC_CACHED = "Cached historical data (Yahoo Finance)"
SRC_SYNTHETIC = "SYNTHETIC demo data (not real prices)"
