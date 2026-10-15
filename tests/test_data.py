from datetime import date

import numpy as np
import pandas as pd
import pytest

import config
from src import data_sources as ds
from src.data_validation import clean_ohlcv


@pytest.fixture(autouse=True)
def tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW_DIR", str(tmp_path / "raw"))
    (tmp_path / "raw").mkdir()
    monkeypatch.setattr(config, "YF_BACKOFF_SECONDS", 0.0)


def fake_yf_frame(start, end):
    idx = pd.bdate_range(start, end, tz="Asia/Kolkata")
    cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], ["ABC.NS"]])
    data = np.column_stack([np.full(len(idx), 100.0), np.full(len(idx), 101.0), np.full(len(idx), 99.0),
                            np.linspace(100, 110, len(idx)), np.full(len(idx), 5e5)])
    return pd.DataFrame(data, index=idx, columns=cols)


def test_download_standardises_and_caches():
    calls = []

    def dl(sym, **kw):
        calls.append(sym)
        return fake_yf_frame(kw["start"], kw["end"])

    b = ds.get_data("ABC.NS", date(2024, 1, 1), date(2024, 3, 29), mode="auto", downloader=dl)
    assert b.status == "LIVE" and not b.is_synthetic
    assert list(b.df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert b.df.index.tz is None
    # second request is served from cache without calling the downloader
    b2 = ds.get_data("ABC.NS", date(2024, 1, 1), date(2024, 3, 29), mode="auto", downloader=dl)
    assert b2.status == "CACHED" and len(calls) == 1
    assert len(b2.df) == len(b.df)


def test_retries_then_falls_back_to_cache_then_synthetic():
    attempts = {"n": 0}

    def failing(sym, **kw):
        attempts["n"] += 1
        raise RuntimeError("429 Too Many Requests")

    b = ds.get_data("NOPE.NS", date(2024, 1, 1), date(2024, 6, 28), mode="auto", downloader=failing)
    assert attempts["n"] == config.YF_MAX_RETRIES
    assert b.is_synthetic and b.status == "SYNTHETIC"
    assert any("Live download unavailable" in m for m in b.messages)

    # with a partial cache present, the cache is preferred over synthetic data
    ds.save_cache("NOPE.NS", ds.standardise(fake_yf_frame("2024-01-01", "2024-02-28")), {"fetched_at": "2024-03-01T00:00:00"})
    b2 = ds.get_data("NOPE.NS", date(2024, 1, 1), date(2024, 6, 28), mode="auto", downloader=failing)
    assert b2.status == "CACHED" and not b2.is_synthetic


def test_empty_download_is_an_error_not_data():
    b = ds.get_data("EMPTY.NS", date(2024, 1, 1), date(2024, 2, 1), mode="refresh",
                    downloader=lambda s, **k: pd.DataFrame())
    assert b.is_synthetic


def test_synthetic_is_deterministic_and_labelled():
    a, ma = ds.synthetic_ohlcv("X.NS", date(2022, 1, 1), date(2022, 12, 31))
    b, _ = ds.synthetic_ohlcv("X.NS", date(2022, 1, 1), date(2022, 12, 31))
    pd.testing.assert_frame_equal(a, b)
    assert "SYNTHETIC" in ma["label"]
    assert ma["injected_issues"]


def test_cleaning_reports_every_treatment():
    df, _ = ds.synthetic_ohlcv("Y.NS", date(2022, 1, 1), date(2023, 12, 31))
    df.iloc[10, 3] = -5.0                       # invalid close
    df.iloc[20, 0] = np.nan                     # missing open
    shuffled = df.sample(frac=1, random_state=1)
    clean, rep = clean_ohlcv(shuffled, date(2022, 1, 1), date(2023, 12, 31))
    steps = rep.as_frame().set_index("Check")["Rows affected"]
    assert clean.index.is_monotonic_increasing
    assert not clean.index.duplicated().any()
    assert steps["Duplicate timestamps"] == 1
    assert steps["Missing price values"] == 1
    assert steps["Invalid prices (≤0 or outside High–Low)"] >= 1
    assert (clean[["Open", "High", "Low", "Close"]] > 0).all().all()
    assert rep.rows_in - rep.rows_out == 3
    assert rep.coverage["sessions"] == len(clean)


def test_offline_fails_fast_without_retries(monkeypatch):
    monkeypatch.setattr(ds, "yahoo_reachable", lambda timeout=4.0: False)
    with pytest.raises(RuntimeError, match="not reachable"):
        ds.fetch_yfinance("ABC.NS", date(2024, 1, 1), date(2024, 2, 1))
    b = ds.get_data("ABC.NS", date(2024, 1, 1), date(2024, 2, 1), mode="refresh")
    assert b.is_synthetic and any("not reachable" in m for m in b.messages)
