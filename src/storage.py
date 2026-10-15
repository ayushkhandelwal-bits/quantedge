"""SQLite persistence of backtest runs (inputs, data status and headline metrics).

Market data itself is cached as CSV in data/raw (see data_sources); this database stores
results so runs are reproducible and comparable later.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import pandas as pd

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT, symbol TEXT, strategy TEXT, params TEXT,
    start TEXT, end TEXT, data_status TEXT, execution TEXT, allow_short INTEGER,
    capital REAL, total_return REAL, cagr REAL, sharpe REAL, max_drawdown REAL,
    trades INTEGER, total_costs REAL, metrics_json TEXT
)"""


def _conn(path: str | None = None):
    con = sqlite3.connect(path or config.DB_PATH)
    con.execute(SCHEMA)
    return con


def save_run(symbol, strategy, params, start, end, data_status, execution, allow_short, capital, m: dict,
             path: str | None = None) -> int:
    clean = {k: (str(v) if not isinstance(v, (int, float, type(None), str)) else v) for k, v in m.items()}
    with _conn(path) as con:
        cur = con.execute(
            "INSERT INTO runs (created_at,symbol,strategy,params,start,end,data_status,execution,allow_short,capital,"
            "total_return,cagr,sharpe,max_drawdown,trades,total_costs,metrics_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), symbol, strategy, json.dumps(params), str(start), str(end),
             data_status, execution, int(allow_short), capital, m.get("total_return"), m.get("cagr"), m.get("sharpe"),
             m.get("max_drawdown"), m.get("trades"), m.get("total_costs"), json.dumps(clean)))
        return int(cur.lastrowid)


def load_runs(limit: int = 50, path: str | None = None) -> pd.DataFrame:
    with _conn(path) as con:
        return pd.read_sql_query(
            "SELECT run_id, created_at, symbol, strategy, params, start, end, data_status, total_return, sharpe, "
            "max_drawdown, trades FROM runs ORDER BY run_id DESC LIMIT ?", con, params=(limit,))
