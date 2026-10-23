"""模块 1 任务 2 补充：用 FNSPID 自带的 `Stock_price/full_history.zip`（2023 年末从 Yahoo 抓取，含当时的退市股）补 yfinance 拿不到的价格。

- 缺失名单 = 成分股全集中没有 `<ticker>.csv` 的代码；在 zip 的 `full_history/<name>.csv` 里按 ticker、'.'→'-'、去掉 '.' 找。
  不用别名：zip 里同一个文件可能拼接了先后使用同一代码的不同公司（见下），别名只会放大这个风险。
- 已知 zip 的坑：
  1. 不少文件是两次抓取拼接的（旧段止于 2020-07-02 或 2020-04-01），旧段没有按之后的拆股调整（AAPL 在 2020-07-02/07-06 之间有 4 倍断点）；
  2. 代码复用：FI.csv 前段是 Frank's International、后段才是 Fiserv（46 倍断点）；CTRA.csv 前段是 Contura Energy、后段才是 Coterra（5.5 倍）；
     PLL.csv 是 Piedmont Lithium 而不是成分股 Pall，ALTR.csv 是 Altair 而不是 Altera。
  对策：只保留该代码在成分股区间内（前推 LOOKBACK_DAYS 天供 Alpha158 回看、后推 LABEL_DAYS 天供标签）的行；
  拼接处（2020-07-02→07-06、2020-04-01→04-02）若 |log 收益| > 0.4，丢掉拼接前的全部行；末行离群值丢弃；
  "跳 ±40% 后下一天跳回"的乒乓错行把当天 OHLC 置 NaN。剩余 |日对数收益| > 0.4 的日子写进 _meta/fnspid_fill.json 供人工核对。
- 转换成与 download_prices 相同的 schema：date, symbol, open, high, low, close, volume, adj_close, factor=adj_close/close，日期升序，裁到 [START, END]。
  FNSPID 的 adj close 以 2023 年末为基准、yfinance 的以下载日为基准：同一只股票只用一个来源，factor 的常数差不影响收益率。
- 来源写进 `_meta/sources.json`（ticker -> fnspid_full_history），之后重算覆盖率报告。
运行：python -m data.fill_prices_fnspid [--dry-run]
"""
from __future__ import annotations

import argparse
import io
import json
import math
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from common import ROOT, load_paths
from data.download_prices import END, START, coverage_report

ZIP_MEMBER = "Stock_price/full_history.zip"
LOOKBACK_DAYS, LABEL_DAYS = 120, 10
STITCHES = [("2020-07-02", "2020-07-06"), ("2020-04-01", "2020-04-02")]


def candidates(ticker: str) -> list[str]:
    return list(dict.fromkeys([ticker, ticker.replace(".", "-"), ticker.replace(".", "")]))


def restrict_to_intervals(df: pd.DataFrame, intervals: list[tuple[str, str]],
                          lookback_days: int = LOOKBACK_DAYS, label_days: int = LABEL_DAYS) -> pd.DataFrame:
    """只保留落在任一成分股区间 [start - lookback, end + label] 内的行（防止同代码的其他公司数据混入）。"""
    d = pd.to_datetime(df["date"])
    keep = pd.Series(False, index=df.index)
    for s, e in intervals:
        keep |= (d >= pd.Timestamp(s) - pd.Timedelta(days=lookback_days)) & (d <= pd.Timestamp(e) + pd.Timedelta(days=label_days))
    return df[keep].reset_index(drop=True)


def drop_before_stitch(df: pd.DataFrame, max_abs_logret: float = 0.4) -> tuple[pd.DataFrame, str | None]:
    """两次抓取的拼接处若有断点，丢掉拼接前的全部行；返回 (df, 丢弃截止日期或 None)。"""
    dates = df["date"].to_list()
    for before, after in STITCHES:
        if before in dates and after in dates:
            i, j = dates.index(before), dates.index(after)
            r = abs(math.log(float(df["close"].iloc[j]) / float(df["close"].iloc[i])))
            if r > max_abs_logret:
                return df.iloc[j:].reset_index(drop=True), before
    return df, None


def trim_trailing_outlier(df: pd.DataFrame, max_abs_logret: float = 0.4) -> pd.DataFrame:
    """最后一行相对前一行 |log 收益| 过大时丢弃（抓取末尾的坏行）。"""
    if len(df) >= 2:
        r = abs(math.log(float(df["close"].iloc[-1]) / float(df["close"].iloc[-2])))
        if r > max_abs_logret:
            return df.iloc[:-1].reset_index(drop=True)
    return df


def repair_pingpong(df: pd.DataFrame, max_abs_logret: float = 0.4, tol: float = 0.1) -> tuple[pd.DataFrame, list[str]]:
    """抓取错误的典型形态：某天价格跳 ±40% 以上、下一天几乎原样跳回（两段对数收益之和 ≈ 0）。
    这不是真实行情（真实暴跌不会次日精确回补），把这一天的 OHLC 置为 NaN（成交量保留），返回被置空的日期。"""
    c = df["close"].astype(float).to_numpy()
    lr = np.diff(np.log(c))
    bad = [i + 1 for i in range(len(lr) - 1)
           if abs(lr[i]) > max_abs_logret and abs(lr[i + 1]) > max_abs_logret and abs(lr[i] + lr[i + 1]) < tol]
    if bad:
        df = df.copy()
        df.loc[df.index[bad], ["open", "high", "low", "close", "adj_close"]] = np.nan
    return df, [df["date"].iloc[i] for i in bad]


def extreme_moves(df: pd.DataFrame, max_abs_logret: float = 0.4) -> list[tuple[str, float]]:
    c = df["close"].astype(float).to_numpy()
    c = c[~np.isnan(c)]; dates = df["date"][df["close"].notna()].to_list()
    lr = np.diff(np.log(c))
    return [(dates[i + 1], round(float(np.exp(lr[i])), 3)) for i in np.where(np.abs(lr) > max_abs_logret)[0]]


def convert_fnspid(df: pd.DataFrame, symbol: str, start: str = START, end: str = END) -> pd.DataFrame:
    df = df.rename(columns={c: c.strip().lower() for c in df.columns}).rename(columns={"adj close": "adj_close"})
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df[(df["date"] >= start) & (df["date"] <= end)].dropna(subset=["close"]).drop_duplicates("date").sort_values("date")
    df.insert(1, "symbol", symbol)
    df["factor"] = df["adj_close"] / df["close"]
    return df[["date", "symbol", "open", "high", "low", "close", "volume", "adj_close", "factor"]].reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh-fnspid", action="store_true", help="重写 _meta/sources.json 里来源为 fnspid 的 CSV（修复规则变了时用）")
    args = ap.parse_args()
    paths = load_paths()
    prices = Path(paths["raw"]["prices_csv"])
    zpath = Path(paths["raw"]["fnspid_news"]) / ZIP_MEMBER
    mem = pl.read_parquet(Path(paths["raw"]["universe"]) / "sp500_membership.parquet")
    sources_path = prices / "_meta" / "sources.json"
    sources = json.loads(sources_path.read_text()) if sources_path.exists() else {}
    have = {p.stem for p in prices.glob("*.csv")}
    if args.refresh_fnspid:
        have -= {t for t, src in sources.items() if src == "fnspid_full_history"}
    missing = sorted(set(mem["ticker"]) - have)
    z = zipfile.ZipFile(zpath)
    names = {n.split("/")[-1][:-4]: n for n in z.namelist() if n.startswith("full_history/") and n.endswith(".csv")}
    print(f"zip has {len(names)} tickers; {len(missing)} missing in {prices}")
    filled, unmatched = {}, []
    for t in missing:
        hit = next((c for c in candidates(t) if c in names), None)
        if hit is None:
            unmatched.append(t); continue
        df = convert_fnspid(pd.read_csv(io.BytesIO(z.read(names[hit]))), t)
        df, cut = drop_before_stitch(df)
        iv = [(str(a), str(b)) for a, b in mem.filter(pl.col("ticker") == t).select("start", "end").rows()]
        df = trim_trailing_outlier(restrict_to_intervals(df, iv))
        if len(df) < 20:
            unmatched.append(t); continue
        df, repaired = repair_pingpong(df)
        filled[t] = {"zip_name": hit, "rows": len(df), "first": df["date"].iloc[0], "last": df["date"].iloc[-1],
                     "dropped_before_stitch": cut, "pingpong_blanked": repaired, "extreme_moves": extreme_moves(df)}
        if not args.dry_run:
            df.to_csv(prices / f"{t}.csv", index=False)
            sources[t] = "fnspid_full_history"
    print(f"matched {len(filled)}, unmatched {len(unmatched)}: {unmatched}")
    if args.dry_run:
        print(json.dumps(filled, indent=1)[:3000]); return
    if args.refresh_fnspid:
        for t in [t for t, src in sources.items() if src == "fnspid_full_history" and t not in filled]:
            (prices / f"{t}.csv").unlink(missing_ok=True); sources.pop(t)
    sources_path.parent.mkdir(exist_ok=True)
    sources_path.write_text(json.dumps(sources, indent=2, sort_keys=True) + "\n")
    (prices / "_meta" / "fnspid_fill.json").write_text(json.dumps({"filled": filled, "unmatched": unmatched}, indent=2) + "\n")
    coverage_report(prices, Path(paths["raw"]["universe"]) / "sp500_membership.parquet", ROOT / paths["results"] / "prices")


if __name__ == "__main__":
    main()
