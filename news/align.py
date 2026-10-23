"""模块 2 任务 7–8：分层时间对齐（plan.md 第 6 节 feature_day 的向量化实现）。

输入：美东时间戳 ts_et（naive，America/New_York 本地时间；day 精度的记录是日历日期 00:00，由调用方直接取 FNSPID 的日期、
不做 UTC→ET 转换）与 time_precision ∈ {second, day}，交易日历（升序日期数组）。
day 精度日期的含义：若 FNSPID 的日期是美东日期，对齐精确；若其实是 UTC 日期（盘后 20:00 ET 之后发布的会记成次日），
我们只会把信号再推迟一个交易日，不会提前，所以没有前视偏差。
主口径（9:00 ET）：令 τ = ts_et（day 精度的记录令 τ = 当日 23:59:59）；找到第一个满足 τ < d 09:00 的交易日 d，
  特征日 t = d 的前一个交易日。标签是 t+1 开盘买入、t+2 开盘卖出，即在 d 开盘建仓。
稳健口径（16:00 ET）：second 精度：第一个满足 τ < d 16:00 的交易日 d，特征日 t = d（16:00 前归当日，其余归下一交易日）；
  day 精度与主口径相同。
前视偏差红线：day 精度一律 23:59:59，绝不能视为 00:00（会把盘后新闻算进当天开盘）。
日历范围之外（τ 早于首个交易日或晚于最后一个交易日）返回 NaT，由调用方剔除并计数。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

ET = "America/New_York"
DAY_END = np.timedelta64(23 * 3600 + 59 * 60 + 59, "s")
NINE = np.timedelta64(9 * 3600, "s")
SIXTEEN = np.timedelta64(16 * 3600, "s")


def to_et(ts_utc: pl.Expr) -> pl.Expr:
    """UTC 时间戳 → naive 美东本地时间（自动处理夏令时）。"""
    return ts_utc.dt.replace_time_zone("UTC").dt.convert_time_zone(ET).dt.replace_time_zone(None)


def load_calendar_from_prices(csv_path: Path) -> np.ndarray:
    """用 SPY 的交易日作为日历（开发期；最终换 Qlib D.calendar()）。返回升序 datetime64[D]。"""
    d = pl.read_csv(csv_path, columns=["date"])["date"].str.to_date().unique().sort()
    return d.to_numpy().astype("datetime64[D]")


def _tau(ts_et: np.ndarray, precision: np.ndarray) -> np.ndarray:
    ts = ts_et.astype("datetime64[s]")
    day_end = ts.astype("datetime64[D]").astype("datetime64[s]") + DAY_END
    return np.where(precision == "day", day_end, ts)


def _first_trading_day_after(cal: np.ndarray, k: np.ndarray) -> np.ndarray:
    """对每个日期 k 返回日历中第一个 > k 的交易日的下标（可能 == len(cal)）。"""
    return np.searchsorted(cal, k, side="right")


def feature_days(ts_et: np.ndarray, precision: np.ndarray, cal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """返回 (主口径特征日, 16:00 口径特征日)，datetime64[D]，越界为 NaT。"""
    cal = np.asarray(cal).astype("datetime64[D]")
    tau = _tau(ts_et, precision)
    nat = np.datetime64("NaT", "D")

    # 主口径：d = 第一个满足 tau < d 09:00 的交易日 ⇔ d > floor(tau - 9h)；t = d 的前一个交易日
    k9 = (tau - NINE).astype("datetime64[D]")
    idx_d = _first_trading_day_after(cal, k9)
    ok = (idx_d >= 1) & (idx_d < len(cal))
    t_main = np.full(len(tau), nat)
    t_main[ok] = cal[idx_d[ok] - 1]

    # 16:00 口径：second 精度 → d = 第一个满足 tau < d 16:00 的交易日，t = d；day 精度与主口径相同
    k16 = (tau - SIXTEEN).astype("datetime64[D]")
    idx16 = _first_trading_day_after(cal, k16)
    ok16 = idx16 < len(cal)
    t_close = np.full(len(tau), nat)
    t_close[ok16] = cal[idx16[ok16]]
    t_1600 = np.where(precision == "day", t_main, t_close)
    t_1600 = np.where(ok, t_1600, nat)
    return t_main, t_1600


def next_trading_days(cal: np.ndarray, t: np.ndarray, k: int = 1) -> np.ndarray:
    """t 之后第 k 个交易日（用于标签 t+1 / t+2 与测试）。"""
    idx = np.searchsorted(cal, t, side="left") + k
    out = np.full(len(t), np.datetime64("NaT", "D"))
    ok = idx < len(cal)
    out[ok] = cal[idx[ok]]
    return out
