"""模块 1 任务 2、4：yfinance 日频 OHLCV 下载到卷上的 CSV 缓存（每只一个文件），供 Qlib dump_bin 使用。

- 股票池：results/universe/sp500_tickers_2015_2023.txt 全集 + SPY（基准）。
- 代码：成分股表的点号记法换成 yfinance 的连字符（BRK.B -> BRK-B）；data/ticker_aliases.yaml 里的历史代码用现用代码取全部历史，
  文件仍按成分股表的代码命名（FB.csv 与 META.csv 内容相同，各自的在池区间由 instruments/sp500.txt 决定）。
- 下载：每批 BATCH 只，批间 sleep，auto_adjust=False 拿到未复权价与 Adj Close；失败的单只重试 RETRIES 次（指数退避）。
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
BATCH, SLEEP, RETRIES = 25, 1.5, 3
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
    got: dict[str, pd.DataFrame] = {}
    for i in range(0, len(syms), batch):
        chunk = syms[i:i + batch]
        try:
            got.update(fetch_batch(chunk, start, end))
        except Exception as e:  # 整批失败也不中断，留给单只重试
            print(f"batch {i // batch + 1} failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
        print(f"batch {i // batch + 1}/{(len(syms) + batch - 1) // batch}: {len(got)} symbols so far", flush=True)
        time.sleep(sleep)
    missing = [s for s in syms if s not in got]
    for s in missing:
        for k in range(retries):
            time.sleep(sleep * (2 ** k))
            try:
                r = fetch_batch([s], start, end)
            except Exception as e:
                print(f"retry {k + 1} {s}: {type(e).__name__}: {str(e)[:100]}", flush=True)
                continue
            if s in r:
                got[s] = r[s]
                break
    failed = []
    rows: dict[str, dict] = {}
    for s, ts in yf_to_tickers.items():
        if s not in got:
            failed.extend((t, s) for t in ts)
            continue
        for t in ts:
            df = tidy(got[s], t)
            df.to_csv(out_dir / f"{t}.csv", index=False)
            rows[t] = {"yf": s, "rows": len(df), "first": df["date"].iloc[0], "last": df["date"].iloc[-1]}
    manifest = {"start": start, "end": end, "n_tickers": len(tickers), "n_cached": len(tickers) - len(todo),
                "n_downloaded": len(rows), "n_failed": len(failed), "failed": [t for t, _ in failed],
                "downloaded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "per_ticker": rows}
    (out_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    pd.DataFrame(failed, columns=["ticker", "yf_symbol"]).to_csv(out_dir / "_failed.csv", index=False)
    print(f"downloaded {len(rows)}, failed {len(failed)}: {[t for t, _ in failed][:40]}", flush=True)
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default=None, help="逗号分隔；默认成分股全集 + SPY")
    ap.add_argument("--out", default=None, help="默认 paths.raw.prices_csv")
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    args = ap.parse_args()
    paths = load_paths()
    if args.tickers:
        tickers = args.tickers.split(",")
    else:
        tickers = [t.strip() for t in (ROOT / paths["results"] / "universe" / "sp500_tickers_2015_2023.txt").read_text().splitlines() if t.strip()]
        tickers.append("SPY")
    download(tickers, Path(args.out or paths["raw"]["prices_csv"]), args.start, args.end)


if __name__ == "__main__":
    main()
