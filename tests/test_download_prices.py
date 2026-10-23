import numpy as np
import pandas as pd

from data.download_prices import tidy, to_yf


def test_to_yf_dots_and_aliases():
    aliases = {"FB": "META"}
    assert to_yf("BRK.B", aliases) == "BRK-B" and to_yf("BF.B", aliases) == "BF-B"
    assert to_yf("FB", aliases) == "META" and to_yf("AAPL", aliases) == "AAPL"


def test_tidy_columns_factor_and_order():
    idx = pd.to_datetime(["2020-01-03", "2020-01-02", "2020-01-02", "2020-01-06"]).tz_localize("America/New_York")
    df = pd.DataFrame({"Open": [10, 9, 9, np.nan], "High": [11, 10, 10, np.nan], "Low": [9, 8, 8, np.nan],
                       "Close": [10.5, 9.5, 9.5, np.nan], "Volume": [100, 90, 90, np.nan], "Adj Close": [10.0, 9.0, 9.0, np.nan]}, index=idx)
    out = tidy(df, "ABC")
    assert list(out.columns) == ["date", "symbol", "open", "high", "low", "close", "volume", "adj_close", "factor"]
    assert list(out["date"]) == ["2020-01-02", "2020-01-03"]      # 去重、去全空行、升序
    assert (out["symbol"] == "ABC").all()
    assert np.allclose(out["factor"], out["adj_close"] / out["close"])
