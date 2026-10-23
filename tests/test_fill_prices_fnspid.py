import pandas as pd

import numpy as np

from data.fill_prices_fnspid import (candidates, convert_fnspid, drop_before_stitch, extreme_moves, repair_pingpong,
                                     restrict_to_intervals, trim_trailing_outlier)


def test_candidates():
    assert candidates("BRK.B") == ["BRK.B", "BRK-B", "BRKB"] and candidates("AAPL") == ["AAPL"]


def test_trailing_outlier_and_extreme_moves():
    df = pd.DataFrame({"date": ["2020-01-02", "2020-01-03", "2020-01-06"], "close": [100.0, 101.0, 55.0]})
    assert list(trim_trailing_outlier(df)["date"]) == ["2020-01-02", "2020-01-03"]
    assert extreme_moves(df) == [("2020-01-06", 0.545)]
    assert len(trim_trailing_outlier(pd.DataFrame({"date": ["a", "b"], "close": [100.0, 110.0]}))) == 2


def test_convert_fnspid_schema_order_and_range():
    df = pd.DataFrame({"date": ["2023-12-28", "2023-12-27", "2010-01-04"], "open": [3, 2, 1], "high": [3, 2, 1], "low": [3, 2, 1],
                       "close": [3.0, 2.0, 1.0], "adj close": [3.0, 1.9, 0.5], "volume": [30, 20, 10]})
    out = convert_fnspid(df, "XYZ", start="2014-06-01", end="2024-01-31")
    assert list(out.columns) == ["date", "symbol", "open", "high", "low", "close", "volume", "adj_close", "factor"]
    assert list(out["date"]) == ["2023-12-27", "2023-12-28"] and (out["symbol"] == "XYZ").all()
    assert abs(out["factor"].iloc[0] - 0.95) < 1e-12


def test_repair_pingpong_blanks_glitch_but_keeps_real_crash():
    df = pd.DataFrame({"date": [f"d{i}" for i in range(6)], "open": 1.0, "high": 1.0, "low": 1.0,
                       "close": [100.0, 100.0, 50.0, 100.0, 60.0, 61.0], "adj_close": 1.0, "volume": 1})
    out, blanked = repair_pingpong(df)
    assert blanked == ["d2"]                              # 跳到 50 又跳回 100：错行
    assert np.isnan(out.loc[2, "close"]) and out.loc[4, "close"] == 60.0   # 真实暴跌（60 之后没有回补）保留
    assert extreme_moves(out) == [("d4", 0.6)]


def test_restrict_to_intervals_and_stitch():
    df = pd.DataFrame({"date": ["2020-06-30", "2020-07-01", "2020-07-02", "2020-07-06", "2020-07-07", "2021-11-01"],
                       "close": [3.5, 3.6, 3.6, 100.0, 101.0, 105.0]})
    out, cut = drop_before_stitch(df)                      # 3.6 -> 100：拼接处断点，丢掉前段
    assert cut == "2020-07-02" and list(out["date"]) == ["2020-07-06", "2020-07-07", "2021-11-01"]
    same, cut2 = drop_before_stitch(pd.DataFrame({"date": ["2020-07-02", "2020-07-06"], "close": [10.0, 10.5]}))
    assert cut2 is None and len(same) == 2
    r = restrict_to_intervals(df, [("2021-10-04", "2023-12-31")], lookback_days=120, label_days=10)
    assert list(r["date"]) == ["2021-11-01"]               # 2020 年的行不在 Coterra 的成分股窗口内
