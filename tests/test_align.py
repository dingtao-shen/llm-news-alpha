"""分层对齐：周末、节假日、9:00 边界、23:59 规则、16:00 口径、越界。日历手写：2024-01-12（周五）… 含 1 月 15 日 MLK 休市。"""
import numpy as np
import polars as pl

from news.align import feature_days, next_trading_days, to_et

CAL = np.array(["2024-01-10", "2024-01-11", "2024-01-12", "2024-01-16", "2024-01-17", "2024-01-18"], dtype="datetime64[D]")
D = np.datetime64


def fd(ts: str, precision: str):
    t, t16 = feature_days(np.array([ts], dtype="datetime64[s]"), np.array([precision]), CAL)
    return t[0], t16[0]


def test_timed_rows_open_cutoff():
    # 周四 08:59:59 → 当日 9:00 前 → d = 周四，t = 周三；周四开盘建仓
    assert fd("2024-01-11T08:59:59", "second")[0] == D("2024-01-10")
    # 周四 09:00:00 整 → 不早于 9:00 → d = 周五，t = 周四
    assert fd("2024-01-11T09:00:00", "second")[0] == D("2024-01-11")
    # 周四 10:30 → t = 周四
    assert fd("2024-01-11T10:30:00", "second")[0] == D("2024-01-11")
    # 周五 17:00 → d = 下周二（周一 MLK 休市），t = 周五
    assert fd("2024-01-12T17:00:00", "second")[0] == D("2024-01-12")
    # 周六 12:00 → d = 周二，t = 周五
    assert fd("2024-01-13T12:00:00", "second")[0] == D("2024-01-12")
    # 周一（休市）08:00 → d = 周二，t = 周五
    assert fd("2024-01-15T08:00:00", "second")[0] == D("2024-01-12")
    # 周二 08:00 → d = 周二，t = 周五（周一不是交易日）
    assert fd("2024-01-16T08:00:00", "second")[0] == D("2024-01-12")


def test_day_rows_are_2359():
    # 仅日期：周四 → 23:59:59 → d = 周五，t = 周四（而不是把 00:00 算进周四开盘 → t = 周三）
    assert fd("2024-01-11T00:00:00", "day")[0] == D("2024-01-11")
    # 周六仅日期 → t = 周五；周一休市仅日期 → d = 周二，t = 周五
    assert fd("2024-01-13T00:00:00", "day")[0] == D("2024-01-12")
    assert fd("2024-01-15T00:00:00", "day")[0] == D("2024-01-12")
    # 16:00 口径对 day 精度与主口径相同
    assert fd("2024-01-11T00:00:00", "day") == (D("2024-01-11"), D("2024-01-11"))


def test_close_cutoff_for_timed_rows():
    # 周四 08:00：主口径 t = 周三（周四开盘建仓）；16:00 口径归当日 → t = 周四
    assert fd("2024-01-11T08:00:00", "second") == (D("2024-01-10"), D("2024-01-11"))
    # 周四 15:59:59 → 两口径都是周四
    assert fd("2024-01-11T15:59:59", "second") == (D("2024-01-11"), D("2024-01-11"))
    # 周四 16:00:00 → 主口径 t = 周四；16:00 口径归下一交易日 → 周五
    assert fd("2024-01-11T16:00:00", "second") == (D("2024-01-11"), D("2024-01-12"))
    # 周五 20:00 → 主口径 t = 周五；16:00 口径 → 下周二
    assert fd("2024-01-12T20:00:00", "second") == (D("2024-01-12"), D("2024-01-16"))


def test_out_of_range_is_nat():
    t, t16 = fd("2024-01-09T12:00:00", "second")        # 早于日历首日 → d = 首日，t 不存在
    assert np.isnat(t) and np.isnat(t16)
    t, t16 = fd("2024-01-18T12:00:00", "second")        # d 超出日历末 → NaT
    assert np.isnat(t) and np.isnat(t16)


def test_labels_next_days():
    t = np.array(["2024-01-12"], dtype="datetime64[D]")
    assert next_trading_days(CAL, t, 1)[0] == D("2024-01-16") and next_trading_days(CAL, t, 2)[0] == D("2024-01-17")


def test_to_et_handles_dst():
    df = pl.DataFrame({"ts": ["2020-01-15 14:30:00", "2020-07-15 14:30:00"]}).with_columns(pl.col("ts").str.to_datetime())
    out = df.select(to_et(pl.col("ts")).alias("et"))["et"].dt.strftime("%Y-%m-%d %H:%M").to_list()
    assert out == ["2020-01-15 09:30", "2020-07-15 10:30"]
