"""模块 2 任务 4：抽样抓原文页面，核对 FNSPID 的时间戳 / 日期。

样本：infra/make_dev_sample.py 抽的 400 条（有时刻 × 仅日期 × benzinga.com × nasdaq.com 各 100）。
抽取页面发布时间：JSON-LD datePublished、og/article:published_time、<time datetime>、pubdate 等；带时区的 ISO 时间转成美东。
比较：
- 有时刻的记录：FNSPID 时间戳按 UTC 解读转美东后与页面时间的差（小时）；若按美东解读的差更接近 0，说明数据卡的 UTC 标注不对。
- 仅日期的记录：页面发布日（美东）− FNSPID 日期（天）。>0 表示 FNSPID 日期早于真实发布（前视风险），<0 表示滞后（只会推迟信号）。
benzinga.com 与 nasdaq.com 对数据中心 IP 返回 Cloudflare 403，所以改从 Wayback Machine 取离 FNSPID 日期最近的快照
（availability API → `web.archive.org/web/<ts>id_/<url>` 原始 HTML）。快照时间本身也是发布时间的上界：快照早于 FNSPID 日期，说明 FNSPID 日期滞后。
输出：results/news/tz_check.csv（逐条）、tz_check.md（汇总）。礼貌抓取：单线程、每请求间隔 2.5 秒、超时 30 秒、429 退避重试。全部 400 条约 40 分钟。
运行：bash infra/run_bg.sh tz-check python -m news.validate_timezone
"""
from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl
import requests

from common import ROOT, load_paths

ET = ZoneInfo("America/New_York")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 llm-news-alpha-research"
PATTERNS = [
    r'"datePublished"\s*:\s*"([^"]+)"',
    r'property="article:published_time"\s+content="([^"]+)"',
    r'content="([^"]+)"\s+property="article:published_time"',
    r'<time[^>]*datetime="([^"]+)"',
    r'name="pubdate"\s+content="([^"]+)"',
    r'"published_at"\s*:\s*"([^"]+)"',
]


def extract_published(html: str) -> str | None:
    for pat in PATTERNS:
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


def parse_iso(s: str) -> datetime | None:
    s = s.strip().replace("Z", "+00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=ET)     # 无时区的按美东（发布方本地）解读，并标记
        except ValueError:
            continue
    return None


def wayback_snapshot(url: str, date_yyyymmdd: str, timeout: int = 30) -> tuple[str | None, str | None]:
    """返回 (离给定日期最近的快照时间戳 YYYYMMDDhhmmss, 原始 HTML 的快照 URL)。"""
    try:
        r = requests.get("https://archive.org/wayback/available", params={"url": url, "timestamp": date_yyyymmdd},
                         headers={"User-Agent": UA}, timeout=timeout)
        snap = r.json().get("archived_snapshots", {}).get("closest")
        if not snap or not snap.get("available"):
            return None, None
        ts = snap["timestamp"]
        return ts, f"https://web.archive.org/web/{ts}id_/{url}"
    except (requests.RequestException, ValueError):
        return None, None


def fetch(url: str, timeout: int = 30, retries: int = 3) -> tuple[int | None, str, str | None]:
    """Wayback 对突发请求返回 429：遇到就退避 15/30/60 秒重试。"""
    for k in range(retries + 1):
        try:
            r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"}, timeout=timeout, allow_redirects=True)
        except requests.RequestException as e:
            return None, f"{type(e).__name__}", None
        if r.status_code != 429 or k == retries:
            return r.status_code, r.url, r.text if r.ok else None
        time.sleep(15 * 2 ** k)
    return None, "429", None


def check_row(row: dict) -> dict:
    day = (row.get("ts_utc") or "")[:10].replace("-", "") or "20200101"
    snap_ts, snap_url = wayback_snapshot(row["Url"], day)
    time.sleep(2.5)
    status, final_url, html = fetch(snap_url) if snap_url else (None, "no-snapshot", None)
    time.sleep(2.5)
    out = {**row, "wayback_ts": snap_ts, "http_status": status, "final_url": final_url, "page_published_raw": None, "page_published_et": None,
           "tz_in_page": None, "title_in_page": None}
    if html:
        raw = extract_published(html)
        out["page_published_raw"] = raw
        if raw:
            d = parse_iso(raw)
            if d:
                out["tz_in_page"] = bool(re.search(r"(Z|[+-]\d\d:?\d\d)$", raw.strip()))
                out["page_published_et"] = d.astimezone(ET).strftime("%Y-%m-%d %H:%M:%S")
        t = (row.get("Article_title") or "").lower()
        words = [w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 3][:6]
        out["title_in_page"] = bool(words) and sum(w in html.lower() for w in words) >= max(1, len(words) // 2)
    return out


def summarize(df: pl.DataFrame) -> str:
    md = ["# FNSPID 时间戳 / 日期校验（抓原文页面）", "",
          f"- 样本 {len(df)} 条；HTTP 200 且解析出发布时间 {int(df['page_published_et'].is_not_null().sum())} 条；"
          f"页面含原标题关键词 {int(df['title_in_page'].fill_null(False).sum())} 条", ""]
    md += ["| has_time | 来源 | 样本 | 抓到页面 | 解析出时间 | 页面带时区 |", "| --- | --- | ---: | ---: | ---: | ---: |"]
    for (ht, host), g in df.group_by(["has_time", "url_host"], maintain_order=True):
        md.append(f"| {ht} | {host} | {len(g)} | {int((g['http_status'] == 200).sum())} | {int(g['page_published_et'].is_not_null().sum())} | {int(g['tz_in_page'].fill_null(False).sum())} |")
    df = df.with_columns(pl.col("page_published_et").cast(pl.Utf8), pl.col("wayback_ts").cast(pl.Utf8), pl.col("tz_in_page").cast(pl.Boolean))
    snap = df.filter(pl.col("wayback_ts").is_not_null()).with_columns(
        pl.col("wayback_ts").str.slice(0, 8).str.to_date("%Y%m%d").alias("snap_date"),
        pl.col("ts_utc").str.slice(0, 10).str.to_date("%Y-%m-%d").alias("fn_date"))
    if len(snap):
        d = (snap["snap_date"] - snap["fn_date"]).dt.total_days()
        md += ["", f"## Wayback 快照（{len(snap)} 条有快照）：快照日 − FNSPID 日期（天）；快照早于 FNSPID 日期的记录说明 FNSPID 日期不早于真实发布",
               f"- <0：{int((d < 0).sum())}，=0：{int((d == 0).sum())}，1–7 天：{int(((d > 0) & (d <= 7)).sum())}，>7 天：{int((d > 7).sum())}"]
    ok = df.filter(pl.col("page_published_et").is_not_null()).with_columns(
        pl.col("page_published_et").str.to_datetime("%Y-%m-%d %H:%M:%S").alias("page_et"),
        pl.col("ts_utc").str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False).alias("fn"))
    timed = ok.filter(pl.col("has_time") == True)
    if len(timed):
        timed = timed.with_columns(
            ((pl.col("fn").dt.replace_time_zone("UTC").dt.convert_time_zone("America/New_York").dt.replace_time_zone(None) - pl.col("page_et")).dt.total_minutes() / 60).alias("diff_if_utc_h"),
            ((pl.col("fn") - pl.col("page_et")).dt.total_minutes() / 60).alias("diff_if_et_h"))
        md += ["", "## 有时刻的记录：FNSPID 时间 − 页面时间（小时）", "", "| 来源 | n | 按 UTC 解读：中位数 / |差|≤0.5h 比例 | 按美东解读：中位数 / |差|≤0.5h 比例 |", "| --- | ---: | ---: | ---: |"]
        for (host,), g in timed.group_by("url_host", maintain_order=True):
            a, b = g["diff_if_utc_h"], g["diff_if_et_h"]
            md.append(f"| {host} | {len(g)} | {a.median():+.2f} / {(a.abs() <= 0.5).mean():.0%} | {b.median():+.2f} / {(b.abs() <= 0.5).mean():.0%} |")
        md += ["", "按 UTC 解读的差值分布（小时，四舍五入）：" + json.dumps(timed["diff_if_utc_h"].round(0).value_counts().sort("diff_if_utc_h").to_dicts(), ensure_ascii=False)]
    day = ok.filter(pl.col("has_time") == False).with_columns(
        (pl.col("page_et").dt.date() - pl.col("fn").dt.date()).dt.total_days().alias("page_minus_fnspid_days"))
    if len(day):
        md += ["", "## 仅日期的记录：页面发布日（美东）− FNSPID 日期（天）", "", "| 来源 | n | =0 | <0（FNSPID 滞后，安全） | >0（FNSPID 早于真实发布，前视风险） | 分布 |", "| --- | ---: | ---: | ---: | ---: | --- |"]
        for (host,), g in day.group_by("url_host", maintain_order=True):
            d = g["page_minus_fnspid_days"]
            md.append(f"| {host} | {len(g)} | {(d == 0).sum()} | {(d < 0).sum()} | {(d > 0).sum()} | {json.dumps(d.value_counts().sort('page_minus_fnspid_days').to_dicts(), ensure_ascii=False)} |")
        md += ["", "页面发布时刻（美东）在当天的分布，看仅日期新闻大多发布在盘中还是盘后：",
               json.dumps(day.with_columns(pl.col("page_et").dt.hour().alias("h")).group_by("h").len().sort("h").to_dicts(), ensure_ascii=False)]
    return "\n".join(md) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(Path(load_paths()["workspace"]) / "data" / "dev_sample" / "tz_check_urls.csv"))
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    rows = pl.read_csv(args.csv, infer_schema_length=0).with_columns(pl.col("has_time") == "true").to_dicts()
    if args.limit:
        rows = rows[: args.limit]
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        out = list(ex.map(check_row, rows))
    df = pl.DataFrame(out)
    res = ROOT / load_paths()["results"] / "news"
    df.write_csv(res / "tz_check.csv")
    md = summarize(df)
    (res / "tz_check.md").write_text(md)
    print(md)
    print(f"done {len(df)} rows in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
