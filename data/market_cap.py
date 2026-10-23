"""模块 1 任务 6：近似历史市值。

- 股数：SEC companyfacts `dei:EntityCommonStockSharesOutstanding`（10-K/10-Q 封面披露），记录 (end=股数截止日, filed=公开日, val)。
  按 **filed** 日期生效（避免前视），取每个交易日前最近一次披露。
- 拆股一致性：披露股数是 end 日的原始股数，而价格是 Yahoo 的拆股调整价（今日口径）。用 yfinance 的拆股事件把股数换算到今日口径：
  shares_today(end) = val × Π(ratio of splits after end)；mcap(d) = shares_today × close_adj(d)。
- ticker → CIK：SEC company_tickers.json（只含现用代码）+ data/ticker_aliases.yaml；退市公司拿不到 CIK，mcap 为空。
- 代理：所有股票都算 adv20 = 20 日平均（close × volume），作为规模代理；报告中注明用哪一个。
- 输出：paths.market_cap（datetime, instrument, shares, mcap, adv20, size_source）与 results/prices/market_cap_coverage.md。
- SEC 访问礼仪：User-Agent 带联系邮箱，≤ 8 请求/秒；JSON 缓存到 paths.sec_dir/companyfacts/，已有的跳过。
运行：bash infra/run_bg.sh market-cap python -m data.market_cap（约 5–8 分钟）
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import requests
import yaml

from common import ROOT, load_paths

UA = "llm-news-alpha research bechillmyfriend@gmail.com"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"


def load_cik_map(sec_dir: Path) -> dict[str, int]:
    f = sec_dir / "company_tickers.json"
    if not f.exists():
        sec_dir.mkdir(parents=True, exist_ok=True)
        f.write_bytes(requests.get(SEC_TICKERS, headers={"User-Agent": UA}, timeout=60).content)
    m = json.loads(f.read_text())
    return {v["ticker"].upper(): int(v["cik_str"]) for v in m.values()}


def cik_for(ticker: str, cik_map: dict[str, int], aliases: dict[str, str]) -> int | None:
    for cand in (ticker, ticker.replace(".", "-"), aliases.get(ticker, ticker), aliases.get(ticker, ticker).replace(".", "-")):
        if cand.upper() in cik_map:
            return cik_map[cand.upper()]
    return None


def fetch_facts(cik: int, cache: Path) -> dict | None:
    f = cache / f"CIK{cik:010d}.json"
    if not f.exists():
        r = requests.get(FACTS.format(cik=cik), headers={"User-Agent": UA}, timeout=60)
        time.sleep(0.13)
        if r.status_code != 200:
            return None
        f.write_bytes(r.content)
    return json.loads(f.read_text())


def shares_records(facts: dict) -> pd.DataFrame:
    """(end, filed, val) 去重：同一 end 取最早 filed；只保留 10-K/10-Q/20-F 等含股数的记录。"""
    try:
        recs = facts["facts"]["dei"]["EntityCommonStockSharesOutstanding"]["units"]["shares"]
    except KeyError:
        return pd.DataFrame(columns=["end", "filed", "val"])
    df = pd.DataFrame(recs)[["end", "filed", "val"]].dropna()
    df["end"] = pd.to_datetime(df["end"]); df["filed"] = pd.to_datetime(df["filed"])
    df = df[df["val"] > 0].sort_values(["filed", "end"]).drop_duplicates("end", keep="first")
    return df.reset_index(drop=True)


def fetch_splits(yf_symbols: list[str], start: str, end: str, batch: int = 50) -> pd.DataFrame:
    """yfinance 拆股事件 (date, yf_symbol, ratio)。"""
    import yfinance as yf
    out = []
    for i in range(0, len(yf_symbols), batch):
        chunk = yf_symbols[i:i + batch]
        try:
            raw = yf.download(chunk, start=start, end=end, actions=True, auto_adjust=False, group_by="ticker", threads=False, progress=False)
        except Exception as e:
            print(f"splits batch {i // batch + 1} failed: {e}", flush=True); continue
        for s in chunk:
            try:
                col = raw[s]["Stock Splits"] if isinstance(raw.columns, pd.MultiIndex) else raw["Stock Splits"]
            except KeyError:
                continue
            col = col.dropna(); col = col[col > 0]
            out.extend({"date": pd.Timestamp(d).tz_localize(None).normalize(), "yf": s, "ratio": float(v)} for d, v in col.items())
        time.sleep(1.0)
    return pd.DataFrame(out, columns=["date", "yf", "ratio"])


def shares_today_basis(rec: pd.DataFrame, splits: pd.DataFrame) -> pd.DataFrame:
    """把每条披露的股数按 end 之后的拆股换算到今日口径。"""
    rec = rec.copy()
    if splits.empty:
        rec["val_today"] = rec["val"]; return rec
    rec["val_today"] = [v * float(np.prod(splits.loc[splits["date"] > e, "ratio"])) for e, v in zip(rec["end"], rec["val"])]
    return rec


def daily_market_cap(prices: pd.DataFrame, rec: pd.DataFrame | None) -> pd.DataFrame:
    """prices: date, close, volume（升序）。返回 date, shares, mcap, adv20。股数按 filed 生效（as-of）。"""
    p = prices.copy()
    p["adv20"] = (p["close"] * p["volume"]).rolling(20, min_periods=10).mean()
    if rec is None or rec.empty:
        p["shares"] = np.nan; p["mcap"] = np.nan
        return p[["date", "shares", "mcap", "adv20"]]
    r = rec.sort_values("filed")[["filed", "val_today"]].rename(columns={"filed": "date", "val_today": "shares"})
    p = pd.merge_asof(p.sort_values("date"), r, on="date", direction="backward")
    p["mcap"] = p["shares"] * p["close"]
    return p[["date", "shares", "mcap", "adv20"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2014-06-01"); ap.add_argument("--end", default="2024-01-31")
    args = ap.parse_args()
    paths = load_paths()
    sec_dir = Path(paths["sec_dir"]); cache = sec_dir / "companyfacts"; cache.mkdir(parents=True, exist_ok=True)
    prices_dir = Path(paths["raw"]["prices_csv"])
    tickers = sorted(p.stem for p in prices_dir.glob("*.csv") if p.stem != "SPY")
    aliases = yaml.safe_load((ROOT / "data" / "ticker_aliases.yaml").read_text())["yfinance"] or {}
    cik_map = load_cik_map(sec_dir)
    ciks = {t: cik_for(t, cik_map, aliases) for t in tickers}
    print(f"{len(tickers)} tickers with prices; CIK found for {sum(v is not None for v in ciks.values())}", flush=True)

    t0 = time.time()
    recs: dict[str, pd.DataFrame] = {}
    for i, (t, cik) in enumerate(ciks.items()):
        if cik is None:
            continue
        facts = fetch_facts(cik, cache)
        if facts:
            recs[t] = shares_records(facts)
        if (i + 1) % 100 == 0:
            print(f"  facts {i + 1}/{len(ciks)} ({time.time() - t0:.0f}s)", flush=True)
    print(f"companyfacts fetched for {len(recs)} tickers, {sum(len(r) > 0 for r in recs.values())} with shares records ({time.time() - t0:.0f}s)", flush=True)

    sp_file = sec_dir / "splits_yfinance.csv"
    if sp_file.exists():
        splits = pd.read_csv(sp_file, parse_dates=["date"])
    else:
        yf_syms = sorted({aliases.get(t, t).replace(".", "-") for t in recs})
        splits = fetch_splits(yf_syms, "2000-01-01", args.end)
        splits.to_csv(sp_file, index=False)
    print(f"splits: {len(splits)} events for {splits['yf'].nunique() if len(splits) else 0} symbols", flush=True)

    frames, cov = [], []
    for t in tickers:
        px = pd.read_csv(prices_dir / f"{t}.csv", usecols=["date", "close", "volume"], parse_dates=["date"]).sort_values("date")
        rec = recs.get(t)
        if rec is not None and len(rec):
            rec = shares_today_basis(rec, splits[splits["yf"] == aliases.get(t, t).replace(".", "-")])
        d = daily_market_cap(px, rec if rec is not None and len(rec) else None)
        d.insert(1, "instrument", t)
        d["size_source"] = np.where(d["mcap"].notna(), "sec_shares_x_close", "adv20_proxy")
        frames.append(d)
        cov.append({"ticker": t, "has_cik": ciks[t] is not None, "n_share_records": 0 if rec is None else len(rec),
                    "mcap_days": int(d["mcap"].notna().sum()), "days": len(d)})
    out = pd.concat(frames)
    out = out[(out["date"] >= args.start) & (out["date"] <= args.end)]
    outp = Path(paths["market_cap"]); outp.parent.mkdir(parents=True, exist_ok=True)
    pl.from_pandas(out.rename(columns={"date": "datetime"})).with_columns(pl.col("datetime").cast(pl.Date)).sort("datetime", "instrument").write_parquet(outp, compression="zstd")
    cv = pd.DataFrame(cov)
    res = ROOT / paths["results"] / "prices"; res.mkdir(parents=True, exist_ok=True)
    cv.to_csv(res / "market_cap_coverage.csv", index=False)
    share = out["mcap"].notna().mean()
    md = ["# 近似历史市值覆盖", "",
          f"- 有价格的股票 {len(tickers)} 只：有 CIK {int(cv.has_cik.sum())}，有股数披露 {int((cv.n_share_records > 0).sum())}，有市值的股票-日 {share:.1%}（其余用 adv20 代理）",
          f"- 拆股事件 {len(splits)} 个（yfinance），用于把披露股数换算到今日口径", f"- 输出 `{outp}`", "",
          "| 年 | 股票-日 | 有市值 | 比例 |", "| --- | ---: | ---: | ---: |"]
    for y, g in out.groupby(out["date"].dt.year):
        md.append(f"| {y} | {len(g):,} | {int(g['mcap'].notna().sum()):,} | {g['mcap'].notna().mean():.1%} |")
    md += ["", "缺市值的股票（无 CIK，多为退市公司）：" + ", ".join(cv[~cv.has_cik].ticker.tolist())]
    (res / "market_cap_coverage.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:8]))


if __name__ == "__main__":
    main()
