import os
import sys
from datetime import date

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture
def synth():
    from src.data_sources import synthetic_ohlcv
    from src.data_validation import clean_ohlcv
    df, _ = synthetic_ohlcv("TEST.NS", date(2020, 1, 1), date(2024, 12, 31))
    clean, _ = clean_ohlcv(df)
    return clean


def make_df(closes, opens=None, start="2024-01-01"):
    idx = pd.bdate_range(start, periods=len(closes), name="Date")
    closes = np.asarray(closes, float)
    opens = closes if opens is None else np.asarray(opens, float)
    return pd.DataFrame({"Open": opens, "High": np.maximum(opens, closes) + 0.5, "Low": np.minimum(opens, closes) - 0.5,
                         "Close": closes, "Volume": 1000.0}, index=idx)
