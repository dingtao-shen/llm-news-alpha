"""data/build_universe.py：区间回放、代码变更保留、多次进出、钳位；再用仓库内真实 YAML 做健全性检查。"""
import datetime as dt
from pathlib import Path

from data.build_universe import (SRC_DIR, Interval, build_intervals, continuity_report, load_year,
                                 members_on)

D = dt.date
Y2015 = {"year": 2015, "tickers_on_Jan_1": ["AAA", "FB", "OLD"], "changes": {
    "2015-03-02": {"difference": ["OLD"], "union": ["NEW"], "confidence_score": 0.9},
}}
Y2016 = {"year": 2016, "tickers_on_Jan_1": ["AAA", "FB", "NEW"], "changes": {
    "2016-06-09": {"difference": ["FB"], "union": ["META"]},   # 同日改代码
    "2016-09-01": {"difference": ["NEW"], "union": []},
    "2016-11-15": {"difference": [], "union": ["NEW"]},       # 退出后再加入
}}


def test_replay_intervals():
    iv = build_intervals([Y2016, Y2015], start=D(2015, 1, 1), end=D(2016, 12, 31))
    assert Interval("AAA", D(2015, 1, 1), D(2016, 12, 31)) in iv
    # 旧代码与新代码都保留，区间相接
    assert Interval("FB", D(2015, 1, 1), D(2016, 6, 8)) in iv
    assert Interval("META", D(2016, 6, 9), D(2016, 12, 31)) in iv
    assert Interval("OLD", D(2015, 1, 1), D(2015, 3, 1)) in iv
    # 两次进出 → 两个区间
    assert [x for x in iv if x.ticker == "NEW"] == [
        Interval("NEW", D(2015, 3, 2), D(2016, 8, 31)), Interval("NEW", D(2016, 11, 15), D(2016, 12, 31))]
    assert members_on(iv, D(2016, 6, 9)) == {"AAA", "META", "NEW"}
    assert members_on(iv, D(2016, 10, 1)) == {"AAA", "META"}
    assert continuity_report([Y2015, Y2016], iv) == []


def test_continuity_detects_mismatch():
    bad = dict(Y2016, tickers_on_Jan_1=["AAA", "FB"])  # 漏了 NEW
    iv = build_intervals([Y2015, bad], start=D(2015, 1, 1), end=D(2016, 12, 31))
    assert continuity_report([Y2015, bad], iv) and "NEW" in continuity_report([Y2015, bad], iv)[0]


def test_real_yaml_sanity():
    files = sorted(Path(SRC_DIR).glob("sp500-ticker-changes-*.yaml"))
    assert len(files) == 9
    years = [load_year(f) for f in files]
    iv = build_intervals(years)
    for day in (D(2015, 1, 1), D(2019, 6, 30), D(2023, 12, 31)):
        assert 450 <= len(members_on(iv, day)) <= 560
    tickers = {x.ticker for x in iv}
    assert {"FB", "META", "GOOG", "GOOGL", "AAPL"} <= tickers
    fb = [x for x in iv if x.ticker == "FB"][0]
    meta = [x for x in iv if x.ticker == "META"][0]
    assert fb.end + dt.timedelta(days=1) == meta.start == D(2022, 6, 9)
    assert all(x.start <= x.end for x in iv)
