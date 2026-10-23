"""端到端：迷你候选集 + 手写日历 → 对齐、长度、去重、in_sp500、面板。"""
import datetime as dt

import numpy as np
import polars as pl

from news.build_clean import build

CAL = np.array(["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08", "2020-01-09", "2020-01-10", "2020-01-13"], dtype="datetime64[D]")


def test_build_pipeline(tmp_path):
    long_body = "word " * 60      # 300 字符
    rows = [
        # news_id, ticker, ts_utc, has_time, title, body
        ("a", "AAPL", "2020-01-03 14:30:00", True, "Apple rises", None),                 # 09:30 ET 周五 → t = 周五
        ("b", "AAPL", "2020-01-04 00:00:00", False, "Apple weekend story", None),         # 周六仅日期 → t = 周五
        ("c", "AAPL", "2020-01-06 12:00:00", False, "Apple short body", "tiny"),         # 正文 < 100 字符 → 剔除
        ("d", "AAPL", "2020-01-07 00:00:00", False, "Apple long piece", long_body),       # 保留
        ("e", "AAPL", "2020-01-08 00:00:00", False, "Apple long piece", long_body + "!"),  # 1 天后几乎相同 → 近似重复
        ("f", "MSFT", "2020-01-08 00:00:00", False, "Apple long piece", long_body),       # 另一只股票 → 保留
        ("g", "AAPL", "2019-12-20 00:00:00", False, "Before calendar", None),             # 日历之前 → 剔除
        ("h", "OLD", "2020-01-09 00:00:00", False, "Old member news", None),              # 特征日在成分股区间之外 → in_sp500 False
    ]
    df = pl.DataFrame({"news_id": [r[0] for r in rows], "ticker": [r[1] for r in rows],
                       "ts_utc": pl.Series([r[2] for r in rows]).str.to_datetime(), "has_time": [r[3] for r in rows],
                       "title": [r[4] for r in rows], "body": [r[5] for r in rows]})
    df = df.with_columns(pl.col("body").is_not_null().alias("has_body"), pl.lit("nasdaq").alias("source_file"))
    cand = tmp_path / "cand.parquet"; df.write_parquet(cand)
    membership = pl.DataFrame({"ticker": ["AAPL", "MSFT", "OLD"], "start": [dt.date(2015, 1, 1)] * 3,
                               "end": [dt.date(2023, 12, 31), dt.date(2023, 12, 31), dt.date(2020, 1, 5)]})
    out, panel, stats = build(cand, CAL, membership, workers=1)
    assert stats["funnel"] == {"candidates": 8, "after_calendar_range": 7, "after_length": 6, "after_near_dup": 5}
    r = {x["news_id"]: x for x in out.to_dicts()}
    assert set(r) == {"a", "b", "d", "f", "h"}
    assert r["a"]["time_precision"] == "second" and r["a"]["ts_et"].hour == 9 and r["a"]["feature_day"] == dt.date(2020, 1, 3)
    assert r["b"]["time_precision"] == "day" and r["b"]["feature_day"] == dt.date(2020, 1, 3)
    # day 精度不做时区转换：2020-01-07 00:00 UTC 是日历日 1 月 7 日，不是 1 月 6 日 19:00 ET
    assert r["d"]["ts_et"] == dt.datetime(2020, 1, 7, 0, 0)
    assert r["d"]["feature_day"] == dt.date(2020, 1, 7) and r["d"]["feature_day_1600"] == dt.date(2020, 1, 7)
    assert r["h"]["in_sp500"] is False and r["a"]["in_sp500"] is True
    p = panel.filter((pl.col("ticker") == "AAPL") & (pl.col("feature_day") == dt.date(2020, 1, 3))).row(0, named=True)
    assert p["news_cnt"] == 2 and p["n_timed"] == 1 and p["n_body"] == 0
