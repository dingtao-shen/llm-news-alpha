"""模块 1 任务 2、4：yfinance 日频 OHLCV 下载到卷上的 CSV 缓存（每只一个文件），供 Qlib dump_bin 使用。

- 股票池：results/universe/sp500_tickers_2015_2023.txt 全集 + SPY（基准）。
- 代码：成分股表的点号记法换成 yfinance 的连字符（BRK.B -> BRK-B）；data/ticker_aliases.yaml 里的历史代码用现用代码取全部历史，
  文件仍按成分股表的代码命名（FB.csv 与 META.csv 内容相同，各自的在池区间由 instruments/sp500.txt 决定）。
- 下载：每批 BATCH 只，批间 sleep，auto_adjust=False 拿到未复权价与 Adj Close；每批下载完立刻写 CSV；
  整批里失败的单只再重试 RETRIES 次（Yahoo 对已退市/改名的代码直接返回"possibly delisted"或"Data doesn't exist"，重试无用，默认只重试 1 次）。
- Yahoo 的 Close 已按拆股调整，Adj Close 再按分红调整，所以 factor 只含分红调整（与 Qlib 官方 Yahoo collector 的口径相同）。
- 结束时按成分股区间统计覆盖率（results/prices/price_coverage.md）：失败的基本是 2024 年前后已被收购 / 私有化 / 改名、Yahoo 不再提供历史的代码。
- 字段：date, symbol, open, high, low, close, volume, adj_close, factor = adj_close / close（Qlib 的复权因子）。
- 断点续跑：已有且非空的 CSV 跳过。结束时写 _manifest.json（成功/失败数、每只行数与日期范围）与 _failed.csv。
- 时间范围：2014-06-01 起（Alpha158 需要约 60 个交易日回看）到 2024-01-31（标签要 t+2 开盘）。

试跑：python -m data.download_prices --tickers AAPL,BRK.B,FB,SPY --out <dir>
全量：bash infra/run_bg.sh prices python -m data.download_prices
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path

import pandas as pd
import yaml

from common import ROOT, load_paths

START, END = "2014-06-01", "2024-01-31"
BATCH, SLEEP, RETRIES = 25, 1.5, 1
FIELDS = ["Open", "High", "Low", "Close", "Volume", "Adj Close"]


def load_aliases() -> dict[str, str]:
    return yaml.safe_load((ROOT / "data" / "ticker_aliases.yaml").read_text())["yfinance"] or {}


def to_yf(ticker: str, aliases: dict[str, str]) -> str:
    return aliases.get(ticker, ticker).replace(".", "-")


def tidy(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """yfinance 单只的 OHLCV 表 -> 规范列；去掉全空行，日期升序。"""
    df = df.copy()
    df.columns = [c if isinstance(c, str) else c[-1] for c in df.columns]
    df = df[FIELDS].dropna(how="all")
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume", "Adj Close": "adj_close"})
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.insert(0, "date", df.index.strftime("%Y-%m-%d"))
    df.insert(1, "symbol", symbol)
    df["factor"] = df["adj_close"] / df["close"]
    return df.reset_index(drop=True)


def fetch_batch(yf_syms: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    import yfinance as yf
    raw = yf.download(yf_syms, start=start, end=end, auto_adjust=False, actions=False, group_by="ticker",
                      threads=False, progress=False)
    out = {}
    if raw is None or raw.empty:
        return out
    for s in yf_syms:
        try:
            sub = raw[s] if isinstance(raw.columns, pd.MultiIndex) else raw
        except KeyError:
            continue
        if isinstance(sub, pd.DataFrame) and not sub.dropna(how="all").empty:
            out[s] = sub
    return out


def download(tickers: list[str], out_dir: Path, start: str = START, end: str = END, batch: int = BATCH,
             sleep: float = SLEEP, retries: int = RETRIES) -> dict:
    aliases = load_aliases()
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [t for t in tickers if not ((out_dir / f"{t}.csv").exists() and (out_dir / f"{t}.csv").stat().st_size > 100)]
    print(f"{len(tickers)} tickers, {len(tickers) - len(todo)} cached, {len(todo)} to download", flush=True)
    yf_to_tickers: dict[str, list[str]] = {}
    for t in todo:
        yf_to_tickers.setdefault(to_yf(t, aliases), []).append(t)
    syms = sorted(yf_to_tickers)
    rows: dict[str, dict] = {}

    def save(s: str, raw: pd.DataFrame) -> None:
        for t in yf_to_tickers[s]:
            df = tidy(raw, t)
            df.to_csv(out_dir / f"{t}.csv", index=False)
            rows[t] = {"yf": s, "rows": len(df), "first": df["date"].iloc[0], "last": df["date"].iloc[-1]}

    got: set[str] = set()
    for i in range(0, len(syms), batch):
        chunk = syms[i:i + batch]
        try:
            for s, raw in fetch_batch(chunk, start, end).items():
                save(s, raw); got.add(s)          # 每批立刻落盘，中断不丢
        except Exception as e:  # 整批失败也不中断，留给单只重试
            print(f"batch {i // batch + 1} failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
        print(f"batch {i // batch + 1}/{(len(syms) + batch - 1) // batch}: {len(got)} symbols so far", flush=True)
        time.sleep(sleep)
    missing = [s for s in syms if s not in got]
    print(f"{len(missing)} symbols missing after batches; retrying {retries}x each", flush=True)
    for s in missing:
        for k in range(retries):
            time.sleep(sleep * (2 ** k))
            try:
                r = fetch_batch([s], start, end)
            except Exception as e:
                print(f"retry {k + 1} {s}: {type(e).__name__}: {str(e)[:100]}", flush=True)
                continue
            if s in r:
                save(s, r[s]); got.add(s)
                break
    failed = [(t, s) for s, ts in yf_to_tickers.items() if s not in got for t in ts]
    manifest = {"start": start, "end": end, "n_tickers": len(tickers), "n_cached": len(tickers) - len(todo),
                "n_downloaded": len(rows), "n_failed": len(failed), "failed": [t for t, _ in failed],
                "downloaded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "per_ticker": rows}
    (out_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    pd.DataFrame(failed, columns=["ticker", "yf_symbol"]).to_csv(out_dir / "_failed.csv", index=False)
    print(f"downloaded {len(rows)}, failed {len(failed)}: {[t for t, _ in failed][:40]}", flush=True)
    return manifest


def coverage_report(out_dir: Path, membership_parquet: Path, res: Path) -> dict:
    """按成分股区间统计价格覆盖：每只是否有 CSV、CSV 是否覆盖其在池区间；按区间结束年份分布。"""
    import polars as pl
    mem = pl.read_parquet(membership_parquet)
    have = {p.stem for p in out_dir.glob("*.csv") if not p.stem.startswith("_")}
    spans = []
    for t in sorted(set(mem["ticker"])):
        if t in have:
            d = pl.read_csv(out_dir / f"{t}.csv", columns=["date"])["date"]
            spans.append({"ticker": t, "has_csv": True, "first": d.min(), "last": d.max(), "rows": len(d)})
        else:
            spans.append({"ticker": t, "has_csv": False, "first": None, "last": None, "rows": 0})
    sp = pl.DataFrame(spans)
    iv = mem.join(sp, on="ticker", how="left").with_columns(
        (pl.col("has_csv") & (pl.col("first").str.to_date() <= pl.col("start") + pl.duration(days=7))
         & (pl.col("last").str.to_date() >= pl.col("end") - pl.duration(days=7))).fill_null(False).alias("covers_interval"))
    by_year = (iv.with_columns(pl.col("end").dt.year().alias("end_year")).group_by("end_year")
                 .agg(pl.len().alias("intervals"), pl.col("has_csv").sum().alias("has_csv"), pl.col("covers_interval").sum().alias("covers"))
                 .sort("end_year"))
    n_t, n_have = sp.height, int(sp["has_csv"].sum())
    md = ["# 价格数据覆盖（yfinance）", "",
          f"- 成分股全集 {n_t} 只，有 CSV {n_have} 只（{n_have / n_t:.1%}）；SPY {'有' if (out_dir / 'SPY.csv').exists() else '无'}",
          f"- 成分股区间 {iv.height} 个，其中价格完整覆盖区间（首末各留 7 天余量）{int(iv['covers_interval'].sum())} 个",
          f"- 失败代码基本是 2024 年及以后被收购 / 私有化 / 改名、Yahoo 已不提供历史的公司；补数据的候选来源：FNSPID 自带的 `Stock_price/full_history.zip`（2023 年抓取，含当时的退市股）", "",
          "| 区间结束年 | 区间数 | 有 CSV | 完整覆盖 |", "| --- | ---: | ---: | ---: |"]
    md += [f"| {r['end_year']} | {r['intervals']} | {r['has_csv']} | {r['covers']} |" for r in by_year.to_dicts()]
    missing_active = iv.filter(~pl.col("has_csv") & (pl.col("end") >= pl.date(2023, 12, 31)))["ticker"].to_list()
    md += ["", f"2023-12-31 仍在池但没有价格的 {len(missing_active)} 只：{', '.join(missing_active)}"]
    res.mkdir(parents=True, exist_ok=True)
    (res / "price_coverage.md").write_text("\n".join(md) + "\n")
    iv.select("ticker", "start", "end", "has_csv", "first", "last", "rows", "covers_interval").write_csv(res / "price_coverage.csv")
    print("\n".join(md))
    return {"n_tickers": n_t, "n_have": n_have, "n_intervals": iv.height, "n_covered": int(iv["covers_interval"].sum())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default=None, help="逗号分隔；默认成分股全集 + SPY")
    ap.add_argument("--out", default=None, help="默认 paths.raw.prices_csv")
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    ap.add_argument("--report-only", action="store_true", help="不下载，只按已有 CSV 写覆盖率报告")
    args = ap.parse_args()
    paths = load_paths()
    out_dir = Path(args.out or paths["raw"]["prices_csv"])
    if args.report_only:
        coverage_report(out_dir, Path(paths["raw"]["universe"]) / "sp500_membership.parquet", ROOT / paths["results"] / "prices")
        return
    if args.tickers:
        tickers = args.tickers.split(",")
    else:
        tickers = [t.strip() for t in (ROOT / paths["results"] / "universe" / "sp500_tickers_2015_2023.txt").read_text().splitlines() if t.strip()]
        tickers.append("SPY")
    download(tickers, out_dir, args.start, args.end)
    if not args.tickers:
        coverage_report(out_dir, Path(paths["raw"]["universe"]) / "sp500_membership.parquet", ROOT / paths["results"] / "prices")


if __name__ == "__main__":
    main()
