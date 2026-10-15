"""Thin orchestration layer used by every dashboard page, so each calculation is defined once."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from src import data_sources as ds
from src import data_validation as dv
from src import performance_metrics as pm
from src.backtester import BacktestConfig, BacktestResult, run_backtest
from src.strategies import REGISTRY


@dataclass
class Dataset:
    bundle: ds.DataBundle
    clean: pd.DataFrame
    report: dv.CleaningReport


def load_dataset(symbol: str, start: date, end: date, mode: str = "auto") -> Dataset:
    b = ds.get_data(symbol, start, end, mode)
    clean, rep = dv.clean_ohlcv(b.df, start, end)
    return Dataset(b, clean, rep)


@dataclass
class StrategyRun:
    key: str
    params: dict
    result: BacktestResult
    metrics: dict


def run_strategy(df: pd.DataFrame, key: str, params: dict, cfg: BacktestConfig, rf: float) -> StrategyRun:
    strat = REGISTRY[key]
    sig = strat.signals(df, params)
    if strat.execution == "open_to_close":
        cfg = BacktestConfig(**{**cfg.__dict__, "execution": "open_to_close"})
    elif cfg.execution == "open_to_close":
        cfg = BacktestConfig(**{**cfg.__dict__, "execution": "next_open"})
    res = run_backtest(df, sig, cfg)
    m = pm.compute_all(res.curve, res.trades, rf, res.equity)
    m["_capital"] = cfg.initial_capital
    return StrategyRun(key, strat.defaults() | params, res, m)
