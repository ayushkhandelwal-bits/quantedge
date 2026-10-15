"""Shared Streamlit UI: theme, sidebar controls, cached computations, formatting and charts.

Calculations are delegated to src/* modules; this file only wires inputs to them and
renders results, so every page shows numbers produced by the same code path.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from src import analysis, storage
from src import performance_metrics as pm
from src import walk_forward as wfm
from src.backtester import BacktestConfig, buy_and_hold_curve
from src.strategies import ENABLED, REGISTRY, TRADING
from src.transaction_costs import CostSchedule

# ------------------------------------------------------------------ palette (dataviz reference instance)
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE, PAGE = "#e1e0d9", "#c3c2b7", "#fcfcfb", "#f9f9f7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
GOOD, WARN, SERIOUS, CRIT = "#0ca30c", "#fab219", "#ec835a", "#d03b3b"
GOOD_TEXT = "#006300"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DIVERGING = [[0, "#d03b3b"], [0.5, "#f0efec"], [1, "#2a78d6"]]
STRAT_COLOR = {k: SERIES[i % len(SERIES)] for i, k in enumerate(["buy_hold"] + TRADING)}

CSS = f"""
<style>
.block-container {{padding-top: 2.2rem; padding-bottom: 2rem; max-width: 1280px;}}
h1, h2, h3 {{letter-spacing: -0.01em; color: {INK};}}
[data-testid="stSidebarLogo"] {{height: 2.1rem; max-width: 100%; width: auto;}}
[data-testid="stSidebarHeader"] {{padding-bottom: 0.4rem;}}
h1 {{font-size: 1.55rem !important; font-weight: 650 !important; margin-bottom: 0 !important;}}
h2 {{font-size: 1.2rem !important; font-weight: 600 !important; margin-top: 1.2rem !important;}}
h3 {{font-size: 1.02rem !important; font-weight: 600 !important;}}
h4 {{font-size: 0.95rem !important; font-weight: 600 !important;}}
.ql-sub {{color: {INK2}; font-size: 0.9rem; margin: 0.15rem 0 0.9rem 0;}}
.ql-kpi {{background: {SURFACE}; border: 1px solid rgba(11,11,11,0.08); border-radius: 10px; padding: 0.75rem 0.9rem; height: 100%;}}
.ql-kpi .lbl {{color: {INK2}; font-size: 0.78rem; font-weight: 500; text-transform: none;}}
.ql-kpi .val {{color: {INK}; font-size: 1.35rem; font-weight: 650; line-height: 1.35;}}
.ql-kpi .note {{color: {MUTED}; font-size: 0.74rem;}}
.ql-badge {{display: inline-block; padding: 0.12rem 0.55rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600;
           border: 1px solid rgba(11,11,11,0.12); margin-right: 0.35rem;}}
.ql-badge.live {{background: #e7f5e7; color: {GOOD_TEXT};}}
.ql-badge.cached {{background: #e8f0fb; color: #184f95;}}
.ql-badge.synthetic {{background: #fff3d6; color: #7a5200;}}
.ql-take {{border-left: 3px solid #2a78d6; background: #f3f7fd; padding: 0.7rem 0.9rem; border-radius: 0 8px 8px 0;
           color: {INK}; font-size: 0.93rem; margin: 0.4rem 0 0.8rem 0;}}
.ql-verdict {{padding: 0.85rem 1rem; border-radius: 10px; border: 1px solid rgba(11,11,11,0.1); margin-bottom: 0.6rem;}}
.ql-verdict .t {{font-weight: 650; font-size: 1.05rem;}}
.ql-foot {{color: {MUTED}; font-size: 0.75rem; margin-top: 1.5rem; border-top: 1px solid {GRID}; padding-top: 0.5rem;}}
.ql-side-author {{margin-top: 0.4rem; line-height: 1.45;}}
.ql-side-author .by {{color: {INK2}; font-size: 0.85rem;}}
.ql-side-author .by b {{color: {INK}; font-weight: 650;}}
.ql-side-author .aff {{color: {INK2}; font-size: 0.8rem;}}
.ql-side-author .icons {{display: flex; gap: 0.75rem; margin-top: 0.45rem;}}
.ql-side-author .icons a {{color: {INK2}; display: inline-flex;}}
.ql-side-author .icons a:hover {{color: #2a78d6;}}
.ql-side-author svg {{width: 20px; height: 20px; stroke: currentColor; fill: none; stroke-width: 1.8;
                     stroke-linecap: round; stroke-linejoin: round;}}
.ql-author {{display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;
            color: {INK2}; font-size: 0.8rem; margin-top: 0.6rem;}}
.ql-author .links {{display: flex; gap: 0.9rem;}}
.ql-author a {{display: inline-flex; align-items: center; gap: 0.3rem; color: {INK2}; text-decoration: none;}}
.ql-author a:hover {{color: #2a78d6;}}
.ql-author svg {{width: 16px; height: 16px; stroke: currentColor; fill: none; stroke-width: 1.8;
                stroke-linecap: round; stroke-linejoin: round;}}
div[data-testid="stMetricValue"] {{font-size: 1.3rem;}}
</style>
"""


# ------------------------------------------------------------------ formatting
def pct(x, d=1, signed=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{x:+.{d}%}" if signed else f"{x:.{d}%}"


def num(x, d=2):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{x:,.{d}f}"


def inr(x, d=0):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    sign = "−" if x < 0 else ""
    return f"{sign}₹{abs(x):,.{d}f}"


# ------------------------------------------------------------------ chart helpers
def style(fig: go.Figure, title: str, y_title: str = "", x_title: str = "", height: int = 380, legend=True) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=INK), x=0, xanchor="left"),
        height=height, margin=dict(l=10, r=10, t=48, b=10 if not legend else 64),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=SURFACE,
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=INK2, size=12),
        hoverlabel=dict(bgcolor="white", font_color=INK, bordercolor=AXIS),
        legend=dict(orientation="h", yanchor="top", y=-0.1 if not x_title else -0.16, xanchor="left", x=0, font=dict(size=11)) if legend else None,
        showlegend=legend, hovermode="x unified",
    )
    fig.update_xaxes(title_text=x_title, gridcolor=GRID, linecolor=AXIS, zeroline=False, showspikes=True, spikecolor=AXIS, spikethickness=1)
    fig.update_yaxes(title_text=y_title, gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS)
    return fig


def candle_fig(df: pd.DataFrame, title: str, overlays: dict | None = None, markers: pd.DataFrame | None = None,
               height=460) -> go.Figure:
    fig = go.Figure(go.Candlestick(x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close, name="Price",
                                   increasing=dict(line=dict(color=GOOD, width=1), fillcolor=GOOD),
                                   decreasing=dict(line=dict(color=CRIT, width=1), fillcolor=CRIT)))
    for i, (name, s) in enumerate((overlays or {}).items()):
        fig.add_trace(go.Scatter(x=s.index, y=s, name=name, mode="lines", line=dict(width=1.6, color=SERIES[(i) % 8])))
    if markers is not None and len(markers):
        for kind, sym, col in (("Buy", "triangle-up", GOOD_TEXT), ("Sell", "triangle-down", CRIT), ("Exit", "circle", INK2)):
            mk = markers[markers["kind"] == kind]
            if len(mk):
                fig.add_trace(go.Scatter(x=mk.index, y=mk["y"], mode="markers", name=kind, text=mk["text"],
                                         hovertemplate="%{text}<extra></extra>",
                                         marker=dict(symbol=sym, size=11, color=col, line=dict(color="white", width=1.5))))
    fig.update_layout(xaxis_rangeslider_visible=False)
    has_legend = bool(overlays) or (markers is not None and len(markers) > 0)
    return style(fig, title, "Price", height=height, legend=has_legend)


def trade_markers(trades: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, t in trades.iterrows():
        e_kind = "Buy" if t["Direction"] == "Long" else "Sell"
        rows.append({"Date": t["Entry date"], "kind": e_kind, "y": df.at[t["Entry date"], "Low"] * 0.985 if e_kind == "Buy" else df.at[t["Entry date"], "High"] * 1.015,
                     "text": f"{e_kind} ({t['Direction'].lower()} entry) @ {t['Entry price']:,.2f} – {t['Entry reason']}"})
        rows.append({"Date": t["Exit date"], "kind": "Exit", "y": df.at[t["Exit date"], "Close"],
                     "text": f"Exit @ {t['Exit price']:,.2f} – {t['Exit reason']} | net {inr(t['Net P&L'])}"})
    return pd.DataFrame(rows).set_index("Date") if rows else pd.DataFrame(columns=["kind", "y", "text"])


# ------------------------------------------------------------------ page chrome
def header(title: str, subtitle: str):
    st.markdown(CSS, unsafe_allow_html=True)
    s = st.session_state
    sel = f"{config.INSTRUMENTS[s.symbol]['name']} ({s.symbol}) · {REGISTRY[s.strategy].name} · {s.start} → {s.end}"
    st.markdown(f"# {title}")
    st.markdown(f"<div class='ql-sub'>{subtitle}<br><b>Current selection:</b> {sel}</div>", unsafe_allow_html=True)


def badge(bundle) -> str:
    cls = bundle.status.lower()
    return f"<span class='ql-badge {cls}'>{bundle.status}</span>"


def data_status_banner(ds: analysis.Dataset):
    b = ds.bundle
    if b.is_synthetic:
        st.warning("**Synthetic demo data in use.** Prices are simulated (regime-switching random walk) so the dashboard works "
                   "offline. Every result on this page illustrates the method only — it says nothing about real markets. "
                   "Use *Refresh from Yahoo Finance* in the sidebar when online.", icon="⚠️")
    for m in b.messages:
        if not b.is_synthetic or "Live download" in m:
            st.caption(f"ℹ️ {m}")


def footer(ds: analysis.Dataset):
    b = ds.bundle
    cov = ds.report.coverage
    st.markdown(
        f"<div class='ql-foot'>{badge(b)} Source: {b.source} · Observations {cov.get('actual_start')} → {cov.get('actual_end')} "
        f"({cov.get('sessions', 0):,} sessions, daily) · Last refresh: {b.fetched_at or 'n/a (not downloaded)'} · "
        f"Risk-free rate {st.session_state.rf:.2%} (assumption) · Past performance does not predict future results.</div>",
        unsafe_allow_html=True)


ICON_MAIL = ("<svg viewBox='0 0 24 24' aria-hidden='true'><rect x='3' y='5' width='18' height='14' rx='2'/>"
             "<path d='M3 7l9 6 9-6'/></svg>")
ICON_PROFILE = ("<svg viewBox='0 0 24 24' aria-hidden='true'><rect x='3' y='3' width='18' height='18' rx='3'/>"
                "<circle cx='12' cy='10' r='3'/><path d='M7 18c1-2.5 3-3.5 5-3.5s4 1 5 3.5'/></svg>")


def sidebar_author():
    """Author credit pinned to the end of the sidebar on every page."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.divider()
    st.markdown(
        f"<div class='ql-side-author'><div class='by'>Built by <b>{config.AUTHOR_NAME}</b></div>"
        f"<div class='aff'>{config.AUTHOR_PROGRAMME} · {config.AUTHOR_AFFILIATION}</div>"
        f"<div class='icons'>"
        f"<a href='{config.AUTHOR_LINKEDIN}' target='_blank' rel='noopener noreferrer' title='LinkedIn profile' aria-label='LinkedIn profile'>{ICON_PROFILE}</a>"
        f"<a href='mailto:{config.AUTHOR_EMAIL}' title='Email {config.AUTHOR_NAME}' aria-label='Email {config.AUTHOR_NAME}'>{ICON_MAIL}</a>"
        f"</div></div>",
        unsafe_allow_html=True)


def kpi(col, label, value, note="", help=None):
    with col:
        st.markdown(f"<div class='ql-kpi' title='{help or ''}'><div class='lbl'>{label}</div><div class='val'>{value}</div>"
                    f"<div class='note'>{note}</div></div>", unsafe_allow_html=True)


def takeaway(text: str):
    import re
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    st.markdown(f"<div class='ql-take'><b>Business takeaway.</b> {text}</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ sidebar & state
MODES = {"Auto: stored data → download → demo": "auto", "Stored data only (offline)": "cache", "Synthetic demo data": "synthetic"}


def init_state():
    s = st.session_state
    defaults = dict(symbol=config.DEFAULT_SYMBOL, benchmark=config.DEFAULT_BENCHMARK, start=config.DEFAULT_START,
                    end=config.DEFAULT_END, mode_label=list(MODES)[0], strategy="sma_crossover", capital=config.INITIAL_CAPITAL,
                    rf=config.RISK_FREE_RATE, execution="next_open", allow_short=False, cost_on=True, slippage_bps=5.0,
                    refresh_token=0, params={})
    for k, v in defaults.items():
        s.setdefault(k, v)


def sidebar():
    s = st.session_state
    with st.sidebar:
        names = {k: f"{v['name']} ({k})" for k, v in config.INSTRUMENTS.items()}
        s.symbol = st.selectbox("Instrument", list(names), index=list(names).index(s.symbol), format_func=names.get)
        c1, c2 = st.columns(2)
        s.start = c1.date_input("Start", s.start, max_value=date.today())
        s.end = c2.date_input("End", s.end, max_value=date.today())
        if s.start >= s.end:
            st.error("Start date must be before end date.")
            st.stop()
        s.mode_label = st.radio("Data source", list(MODES), index=list(MODES).index(s.mode_label),
                                help="Auto uses locally stored Yahoo Finance data when it covers the dates, downloads otherwise, "
                                     "and falls back to clearly labelled synthetic data if both fail.")
        if st.button("↻ Refresh from Yahoo Finance", width="stretch",
                     help="Force a new download for the selected instrument and the benchmark (needs internet)."):
            s.refresh_token += 1
            s._force_refresh = True
            st.cache_data.clear()

        st.divider()
        st.markdown("**Strategy**")
        labels = {k: REGISTRY[k].name for k in ENABLED}
        s.strategy = st.selectbox("Strategy", list(labels), index=list(labels).index(s.strategy), format_func=labels.get,
                                  label_visibility="collapsed")
        strat = REGISTRY[s.strategy]
        params = {}
        for p in strat.params:
            key = f"p_{strat.key}_{p.name}"
            if isinstance(p.default, int) and float(p.step).is_integer():
                params[p.name] = st.slider(p.label, int(p.min), int(p.max), int(st.session_state.get(key, p.default)), int(p.step), key=key)
            else:
                params[p.name] = st.slider(p.label, float(p.min), float(p.max), float(st.session_state.get(key, p.default)), float(p.step), key=key)
        s.params = params
        s.capital = st.number_input("Starting capital (₹)", 10_000.0, 1e9, float(s.capital), 50_000.0, format="%.0f")
        bnames = {k: v["name"] for k, v in config.INSTRUMENTS.items()}
        s.benchmark = st.selectbox("Benchmark index", list(bnames), index=list(bnames).index(s.benchmark), format_func=bnames.get,
                                   help="Shown for context (frictionless buy-and-hold). Classification uses buy-and-hold of the same instrument.")

        with st.expander("Execution & cost assumptions"):
            s.execution = st.radio("Order execution", ["next_open", "same_close"], index=["next_open", "same_close"].index(s.execution),
                                   format_func={"next_open": "Next session's open (realistic)", "same_close": "Signal day's close (optimistic)"}.get)
            s.allow_short = st.checkbox("Allow short positions", s.allow_short,
                                        help="Off by default: overnight short-selling of Indian cash equities is not generally available "
                                             "to retail investors. When on, shorts are modelled like delivery trades (simplification).")
            s.cost_on = st.checkbox("Apply transaction costs", s.cost_on)
            s.slippage_bps = st.slider("Slippage (basis points per side)", 0.0, 50.0, float(s.slippage_bps), 1.0)
            s.rf = st.number_input("Risk-free rate (annual, %)", 0.0, 15.0, float(s.rf * 100), 0.25,
                                   help=config.RISK_FREE_SOURCE) / 100
        st.caption("Data: Yahoo Finance via yfinance (free). Educational analysis, not investment advice.")
    with st.sidebar:
        sidebar_author()


def bt_config() -> BacktestConfig:
    s = st.session_state
    cs = CostSchedule(slippage_bps=s.slippage_bps) if s.cost_on else CostSchedule.zero()
    return BacktestConfig(initial_capital=float(s.capital), allow_short=s.allow_short, execution=s.execution, costs=cs)


# ------------------------------------------------------------------ cached computations
def _mode():
    s = st.session_state
    if s.get("_force_refresh"):
        return "refresh"
    return MODES[s.mode_label]


@st.cache_data(show_spinner="Loading market data…", max_entries=64)
def _load(symbol, start, end, mode, token):
    return analysis.load_dataset(symbol, start, end, mode)


def dataset(symbol: str | None = None) -> analysis.Dataset:
    s = st.session_state
    sym = symbol or s.symbol
    d = _load(sym, s.start, s.end, _mode(), s.refresh_token)
    if d.clean.empty or len(d.clean) < 60:
        st.error(f"Not enough usable observations for {sym} ({len(d.clean)} rows after cleaning). Widen the date range or choose another instrument.")
        st.stop()
    return d


def _cfg_key(cfg: BacktestConfig):
    return tuple(sorted({**asdict(cfg), "costs": tuple(sorted(asdict(cfg.costs).items()))}.items()))


@st.cache_data(show_spinner="Running backtest…", max_entries=256)
def _run(symbol, start, end, mode, token, key, params_items, cfg_key, rf):
    clean = _load(symbol, start, end, mode, token).clean
    cfg = _cfg_from_key(cfg_key)
    return analysis.run_strategy(clean, key, dict(params_items), cfg, rf)


def _cfg_from_key(cfg_key):
    d = dict(cfg_key)
    d["costs"] = CostSchedule(**dict(d["costs"]))
    return BacktestConfig(**d)


def run(key: str | None = None, params: dict | None = None, cfg: BacktestConfig | None = None) -> analysis.StrategyRun:
    s = st.session_state
    key = key or s.strategy
    if params is None:
        params = s.params if key == s.strategy else REGISTRY[key].defaults()
    cfg = cfg or bt_config()
    r = _run(s.symbol, s.start, s.end, _mode(), s.refresh_token, key, tuple(sorted(params.items())), _cfg_key(cfg), s.rf)
    return r


def run_all() -> dict[str, analysis.StrategyRun]:
    """Every enabled strategy (default parameters, except the selected one which uses the sidebar values)."""
    return {k: run(k) for k in ENABLED}


@st.cache_data(show_spinner="Running walk-forward validation…", max_entries=64)
def _wf(symbol, start, end, mode, token, key, cfg_key, rf, train_years, test_months):
    return wfm.walk_forward(_load(symbol, start, end, mode, token).clean, REGISTRY[key], _cfg_from_key(cfg_key), rf, train_years, test_months)


def walk_forward(key=None, train_years=2.0, test_months=6):
    s = st.session_state
    return _wf(s.symbol, s.start, s.end, _mode(), s.refresh_token, key or s.strategy, _cfg_key(bt_config()), s.rf,
               train_years, test_months)


def benchmark_curve(capital: float, index: pd.DatetimeIndex) -> tuple[pd.Series | None, str]:
    s = st.session_state
    try:
        bd = dataset(s.benchmark)
    except Exception:
        return None, ""
    c = bd.clean["Close"].reindex(index).ffill().dropna()
    if len(c) < 2:
        return None, ""
    lbl = config.INSTRUMENTS[s.benchmark]["name"] + (" (SYNTHETIC)" if bd.bundle.is_synthetic else "")
    return buy_and_hold_curve(c, capital), lbl


def log_run(r: analysis.StrategyRun, ds: analysis.Dataset):
    """Persist each distinct run once per session (SQLite)."""
    s = st.session_state
    key = (s.symbol, r.key, tuple(sorted(r.params.items())), s.start, s.end, ds.bundle.status, s.execution, s.allow_short, s.capital)
    logged = s.setdefault("_logged", set())
    if key in logged:
        return
    try:
        storage.save_run(s.symbol, r.key, r.params, s.start, s.end, ds.bundle.status, s.execution, s.allow_short, s.capital, r.metrics)
        logged.add(key)
    except Exception as e:  # noqa: BLE001
        st.caption(f"Could not save run history: {e}")


def after_load():
    """Clear the one-shot refresh flag once a page has loaded data."""
    st.session_state._force_refresh = False


@st.cache_data(show_spinner="Testing parameter sensitivity…", max_entries=64)
def _sens(symbol, start, end, mode, token, key, cfg_key, rf):
    return wfm.sensitivity(_load(symbol, start, end, mode, token).clean, REGISTRY[key], _cfg_from_key(cfg_key), rf)


def sensitivity():
    s = st.session_state
    return _sens(s.symbol, s.start, s.end, _mode(), s.refresh_token, s.strategy, _cfg_key(bt_config()), s.rf)


@st.cache_data(show_spinner="Testing cost sensitivity…", max_entries=64)
def _csens(symbol, start, end, mode, token, key, params_items, cfg_key, rf):
    return wfm.cost_sensitivity(_load(symbol, start, end, mode, token).clean, REGISTRY[key], dict(params_items),
                                _cfg_from_key(cfg_key), rf)


def cost_sensitivity(params: dict):
    """Always relative to the published schedule (+ sidebar slippage), even if costs are switched off in the sidebar."""
    s = st.session_state
    cfg = bt_config()
    cfg = BacktestConfig(**{**cfg.__dict__, "costs": CostSchedule(slippage_bps=s.slippage_bps)})
    return _csens(s.symbol, s.start, s.end, _mode(), s.refresh_token, s.strategy, tuple(sorted(params.items())), _cfg_key(cfg), s.rf)


# ------------------------------------------------------------------ multi-instrument research helpers
@st.cache_data(show_spinner="Detecting patterns across instruments…", max_entries=32)
def _pattern_events(symbols, start, end, mode, token, params_items, entry, cost_pct, oos_fraction, bench):
    import pandas as _pd
    from src import candlestick_patterns as _cp
    from src import pattern_validation as _pv
    params = _cp.PatternParams(**dict(params_items))
    bclose = _load(bench, start, end, mode, token).clean["Close"]
    evs, bases, status = [], {}, {}
    for sym in symbols:
        d = _load(sym, start, end, mode, token)
        status[sym] = d.bundle.status
        evs.append(_pv.stock_events(d.clean, sym, params, entry=entry, cost_pct=cost_pct, bench_close=bclose,
                                    oos_fraction=oos_fraction))
        bases[sym] = _pv.base_rates(d.clean, entry=entry)
    ev = _pd.concat([e for e in evs if len(e)], ignore_index=True) if any(len(e) for e in evs) else _pd.DataFrame()
    return ev, bases, status


def pattern_events(symbols, params, entry, cost_pct, oos_fraction, bench="^NSEI"):
    s = st.session_state
    from dataclasses import asdict as _asdict
    return _pattern_events(tuple(symbols), s.start, s.end, _mode(), s.refresh_token, tuple(sorted(_asdict(params).items())),
                           entry, cost_pct, oos_fraction, bench)


@st.cache_data(show_spinner="Loading instruments…", max_entries=32)
def _closes(symbols, start, end, mode, token):
    out, status = {}, {}
    for sym in symbols:
        d = _load(sym, start, end, mode, token)
        out[sym] = d.clean["Close"]
        status[sym] = d.bundle.status
    return out, status


def closes(symbols):
    s = st.session_state
    return _closes(tuple(symbols), s.start, s.end, _mode(), s.refresh_token)


def synthetic_notice(status: dict):
    syn = [k for k, v in status.items() if v == "SYNTHETIC"]
    if syn:
        st.warning(f"**Synthetic demo data** for: {', '.join(syn)}. Results for these instruments illustrate the method only and "
                   "are not evidence about real markets.", icon="⚠️")


def short_name(sym: str) -> str:
    return config.INSTRUMENTS.get(sym, {}).get("name", sym)
