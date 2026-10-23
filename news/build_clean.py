"""模块 2 任务 5–9：候选集 → 接口文件 1 `news_clean.parquet` 与股票-日面板 `news_panel.parquet`。

流程（各步剔除数写进 results/news/news_clean_report.md）：
 1. 读 paths.news.embed_candidates；ticker 已是成分股表写法（candidates.py 用 news/ticker_map.py 映射）。
 2. 时间：second 精度 ts_utc → 美东 ts_et；day 精度直接取日历日期（00:00:00 UTC 只是占位，不做时区转换）；time_precision = second / day。
 3. 对齐：主口径 feature_day（9:00 ET，day 精度按 23:59:59）与 feature_day_1600（news/align.py）；日历来自 SPY 交易日
    （开发期；最终换 Qlib D.calendar()）。越界（日历首日前 / 末日后）剔除。
 4. 长度：有正文的记录正文不在 [100, 100000] 字符内剔除。
 5. 近似重复：同一股票、前 5 个交易日内词袋余弦 >= 0.8 的后一条剔除。
 6. in_sp500：feature_day 落在该 ticker 的成分股区间内。
 0. 日期修正（DATE_FIXES=True，依据 results/news/tz_check_conclusions.md）：Benzinga 有时刻记录 +8 小时（FNSPID 标注的 "UTC" 实为 UTC−8）；
    剔除 nasdaq.com 的全部有时刻记录与 2023-11-30..2023-12-16 的记录（最后一次抓取按抓取期打标）；nasdaq.com 日期取 max(FNSPID 日期, URL 日期)。
输出列：news_id, ticker, ts_et, time_precision, title, body, has_body, source_file, feature_day, feature_day_1600, in_sp500。
面板：(feature_day, ticker) → news_cnt, n_timed, n_body, in_sp500。
运行：make news-clean（Pod，几分钟）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path

import numpy as np
import polars as pl

from common import ROOT, load_paths, ncpu
from news.align import feature_days, load_calendar_from_prices, to_et
from news.filters import MAX_CHARS, MIN_CHARS, THRESHOLD, WINDOW, near_duplicates_by_group


DATE_FIXES = True
BENZINGA_OFFSET_HOURS = 8
SCRAPE_STAMPED = (dt.date(2023, 11, 30), dt.date(2023, 12, 16))


def load_url_info(parquet_dir: str, news_ids: pl.Series) -> pl.DataFrame:
    """每个 news_id 的 url_host 与 URL 末尾日期（nasdaq.com 的 …-YYYY-MM-DD）。"""
    import duckdb
    con = duckdb.connect(); con.execute("SET enable_progress_bar=false")
    con.register("ids", news_ids.to_frame("news_id").to_arrow())
    return con.execute(rf"""
        SELECT DISTINCT n.news_id, n.url_host,
               try_strptime(regexp_extract(n.Url, '-(\d{{4}}-\d{{2}}-\d{{2}})$', 1), '%Y-%m-%d')::DATE AS url_date
        FROM read_parquet('{parquet_dir}/nasdaq/*.parquet') n JOIN ids USING (news_id)""").pl().unique(subset=["news_id"])


def apply_date_fixes(df: pl.DataFrame, url_info: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """在候选集（ts_utc, has_time）上做日期修正，返回 (df, 各规则影响行数)。"""
    df = df.join(url_info, on="news_id", how="left")
    stats = {}
    is_nasdaq = pl.col("url_host") == "nasdaq.com"
    is_benz = pl.col("url_host") == "benzinga.com"
    drop_timed = is_nasdaq & pl.col("has_time")
    drop_stamped = is_nasdaq & pl.col("ts_utc").dt.date().is_between(SCRAPE_STAMPED[0], SCRAPE_STAMPED[1])
    stats["dropped_nasdaq_timed"] = int(df.select(drop_timed.sum()).item())
    stats["dropped_nasdaq_scrape_stamped"] = int(df.select((drop_stamped & ~drop_timed).sum()).item())
    df = df.filter(~(drop_timed | drop_stamped))
    shift_benz = is_benz & pl.col("has_time")
    stats["benzinga_timed_shifted_8h"] = int(df.select(shift_benz.sum()).item())
    url_later = is_nasdaq & ~pl.col("has_time") & (pl.col("url_date") > pl.col("ts_utc").dt.date())
    stats["nasdaq_date_moved_to_url_date"] = int(df.select(url_later.sum()).item())
    df = df.with_columns(
        pl.when(shift_benz).then(pl.col("ts_utc") + pl.duration(hours=BENZINGA_OFFSET_HOURS))
          .when(url_later).then(pl.col("url_date").cast(pl.Datetime("us")))
          .otherwise(pl.col("ts_utc")).alias("ts_utc"))
    return df.drop("url_host", "url_date"), stats


def add_time_and_alignment(df: pl.DataFrame, cal: np.ndarray) -> pl.DataFrame:
    """second 精度：UTC → 美东；day 精度：FNSPID 的 `YYYY-MM-DD 00:00:00 UTC` 只是日历日期的占位，不能按 UTC 瞬时转换
    （否则会变成前一天 19:00/20:00 ET，把特征日提前一天）。直接取该日期作为美东日历日 c，对齐时按 c 23:59:59 处理。"""
    df = df.with_columns(
        pl.when(pl.col("has_time")).then(to_et(pl.col("ts_utc"))).otherwise(pl.col("ts_utc").dt.date().cast(pl.Datetime("us"))).alias("ts_et"),
        pl.when(pl.col("has_time")).then(pl.lit("second")).otherwise(pl.lit("day")).alias("time_precision"),
    )
    t_main, t_1600 = feature_days(df["ts_et"].to_numpy(), df["time_precision"].to_numpy().astype(str), cal)
    return df.with_columns(pl.Series("feature_day", t_main).cast(pl.Date), pl.Series("feature_day_1600", t_1600).cast(pl.Date))


def add_in_sp500(df: pl.DataFrame, membership: pl.DataFrame) -> pl.DataFrame:
    m = membership.select("ticker", "start", "end")
    hit = (df.select("news_id", "ticker", "feature_day").join(m, on="ticker", how="inner")
             .filter((pl.col("feature_day") >= pl.col("start")) & (pl.col("feature_day") <= pl.col("end")))
             .select("news_id").unique().with_columns(pl.lit(True).alias("in_sp500")))
    return df.join(hit, on="news_id", how="left").with_columns(pl.col("in_sp500").fill_null(False))


def dedup_groups(df: pl.DataFrame, cal: np.ndarray) -> dict[str, list[tuple[str, int, str]]]:
    day_idx = np.searchsorted(cal, df["feature_day"].to_numpy().astype("datetime64[D]"))
    text = (pl.col("title").fill_null("") + pl.lit(" ") + pl.col("body").fill_null("")).alias("text")
    d = df.select("ticker", "news_id", text).with_columns(pl.Series("day", day_idx))
    groups: dict[str, list] = {}
    for t, nid, txt, day in zip(d["ticker"].to_list(), d["news_id"].to_list(), d["text"].to_list(), d["day"].to_list()):
        groups.setdefault(t, []).append((nid, int(day), txt))
    return groups


def build(candidates: Path, cal: np.ndarray, membership: pl.DataFrame, workers: int,
          url_info: pl.DataFrame | None = None) -> tuple[pl.DataFrame, pl.DataFrame, dict]:
    t0 = time.time()
    df = pl.read_parquet(candidates)
    funnel = {"candidates": len(df)}
    fix_stats = {}
    if url_info is not None:
        df, fix_stats = apply_date_fixes(df, url_info)
        funnel["after_date_fixes"] = len(df)
    df = add_time_and_alignment(df, cal)
    n_oob = int(df["feature_day"].is_null().sum())
    df = df.filter(pl.col("feature_day").is_not_null())
    funnel["after_calendar_range"] = len(df)
    df = df.filter(pl.col("body").is_null() | pl.col("body").str.strip_chars().str.len_chars().is_between(MIN_CHARS, MAX_CHARS))
    funnel["after_length"] = len(df)
    t1 = time.time()
    dups = near_duplicates_by_group(dedup_groups(df, cal), workers)
    df = df.filter(~pl.col("news_id").is_in(list(dups)))
    funnel["after_near_dup"] = len(df)
    dedup_secs = time.time() - t1
    df = add_in_sp500(df, membership)
    df = df.select("news_id", "ticker", "ts_et", "time_precision", "title", "body", "has_body", "source_file",
                   "feature_day", "feature_day_1600", "in_sp500").sort("news_id")
    panel = (df.group_by("feature_day", "ticker").agg(pl.len().alias("news_cnt"),
                                                      (pl.col("time_precision") == "second").sum().alias("n_timed"),
                                                      pl.col("has_body").sum().alias("n_body"),
                                                      pl.col("in_sp500").first().alias("in_sp500"))
                .sort("feature_day", "ticker"))
    stats = {"funnel": funnel, "date_fixes": fix_stats, "out_of_calendar": n_oob, "near_dup_removed": len(dups), "dedup_secs": round(dedup_secs, 1),
             "secs": round(time.time() - t0, 1)}
    return df, panel, stats


def describe(df: pl.DataFrame, panel: pl.DataFrame, membership: pl.DataFrame, cal: np.ndarray) -> dict:
    out = {}
    out["by_precision"] = df.group_by("time_precision").len().sort("time_precision").to_dicts()
    out["by_year"] = (df.with_columns(pl.col("feature_day").dt.year().alias("year"))
                        .group_by("year").agg(pl.len().alias("n"), pl.col("has_body").sum().alias("n_body"),
                                              (pl.col("time_precision") == "second").sum().alias("n_timed"),
                                              pl.col("in_sp500").sum().alias("n_in_sp500"))
                        .sort("year").to_dicts())
    out["in_sp500"] = {"true": int(df["in_sp500"].sum()), "false": int((~df["in_sp500"]).sum())}
    # 特征日相对发布日的偏移（day 精度：周末/节假日会推到前一个交易日）
    shift = (df["feature_day"].cast(pl.Datetime) - df["ts_et"].dt.date().cast(pl.Datetime)).dt.total_days()
    out["feature_day_minus_pub_date_days"] = pl.DataFrame({"d": shift}).group_by("d").len().sort("d").to_dicts()
    out["cutoff_1600_differs"] = int((df["feature_day"] != df["feature_day_1600"]).sum())
    per_t = df.group_by("ticker").len()
    out["per_ticker"] = {"n_tickers": len(per_t), "median": float(per_t["len"].median()), "p10": float(per_t["len"].quantile(0.1)),
                         "p90": float(per_t["len"].quantile(0.9)), "max": int(per_t["len"].max())}
    # 股票-日覆盖率：成分股区间内 2015–2023 的交易日中有新闻的比例
    cal_s = pl.Series("d", cal.astype("datetime64[D]")).cast(pl.Date)
    cal_df = pl.DataFrame({"feature_day": cal_s}).filter(pl.col("feature_day").is_between(pl.date(2015, 1, 1), pl.date(2023, 12, 31)))
    sd = (membership.join(cal_df, how="cross").filter((pl.col("feature_day") >= pl.col("start")) & (pl.col("feature_day") <= pl.col("end")))
            .select("ticker", "feature_day").unique())
    with_news = sd.join(panel.filter(pl.col("in_sp500")).select("ticker", "feature_day"), on=["ticker", "feature_day"], how="semi")
    out["stock_days"] = {"total": len(sd), "with_news": len(with_news), "share": round(len(with_news) / len(sd), 4)}
    yr = (sd.with_columns(pl.col("feature_day").dt.year().alias("year")).group_by("year").len().rename({"len": "stock_days"})
            .join(with_news.with_columns(pl.col("feature_day").dt.year().alias("year")).group_by("year").len().rename({"len": "with_news"}), on="year")
            .with_columns((pl.col("with_news") / pl.col("stock_days")).round(4).alias("share")).sort("year"))
    out["stock_days_by_year"] = yr.to_dicts()
    return out


def write_report(stats: dict, desc: dict, meta: dict, res: Path) -> None:
    f = stats["funnel"]
    md = ["# news_clean.parquet（接口文件 1）", "",
          f"- 输出 `{meta['out']}`：**{f['after_near_dup']:,}** 条；面板 `{meta['panel']}`；日历来源 {meta['calendar']}（{meta['calendar_days']} 个交易日，{meta['calendar_range'][0]} 至 {meta['calendar_range'][1]}）",
          f"- 规则：主口径 9:00 ET（day 精度按当日 23:59:59）；16:00 口径；正文长度 [{MIN_CHARS}, {MAX_CHARS:,}]；近似重复阈值 {THRESHOLD}、窗口 {WINDOW} 个交易日；耗时 {stats['secs']} s（去重 {stats['dedup_secs']} s）",
          "", "## 过滤漏斗", "", "| 步骤 | 剩余 | 剔除 |", "| --- | ---: | ---: |",
          f"| 候选集 | {f['candidates']:,} | |",
          *([f"| 日期修正后（剔除 nasdaq.com 有时刻 {stats['date_fixes'].get('dropped_nasdaq_timed', 0):,}、抓取期打标 {stats['date_fixes'].get('dropped_nasdaq_scrape_stamped', 0):,}；"
             f"Benzinga 有时刻 +8h {stats['date_fixes'].get('benzinga_timed_shifted_8h', 0):,}；nasdaq 日期改为 URL 日期 {stats['date_fixes'].get('nasdaq_date_moved_to_url_date', 0):,}） | {f['after_date_fixes']:,} | {f['candidates'] - f['after_date_fixes']:,} |"]
            if "after_date_fixes" in f else []),
          f"| 日历范围内 | {f['after_calendar_range']:,} | {stats['out_of_calendar']:,} |",
          f"| 正文长度 | {f['after_length']:,} | {f['after_calendar_range'] - f['after_length']:,} |",
          f"| 近似重复 | {f['after_near_dup']:,} | {stats['near_dup_removed']:,} |",
          "", "## 精度与口径", "",
          f"- time_precision：{desc['by_precision']}",
          f"- 16:00 口径与主口径特征日不同的记录：{desc['cutoff_1600_differs']:,}（只可能发生在 second 精度）",
          f"- 特征日 − 发布日（天）：{desc['feature_day_minus_pub_date_days']}",
          f"- in_sp500（特征日在该 ticker 的成分股区间内）：{desc['in_sp500']}",
          "", "## 按年", "", "| 年 | 条数 | 有正文 | 有时刻 | in_sp500 |", "| --- | ---: | ---: | ---: | ---: |"]
    md += [f"| {r['year']} | {r['n']:,} | {r['n_body']:,} | {r['n_timed']:,} | {r['n_in_sp500']:,} |" for r in desc["by_year"]]
    pt = desc["per_ticker"]
    md += ["", "## 覆盖", "",
           f"- 每只股票条数：{pt['n_tickers']} 只，中位数 {pt['median']:.0f}，10%/90% 分位 {pt['p10']:.0f} / {pt['p90']:.0f}，最多 {pt['max']:,}",
           f"- 股票-日覆盖率（成分股区间内 2015–2023 交易日有新闻的比例）：{desc['stock_days']['with_news']:,} / {desc['stock_days']['total']:,} = **{desc['stock_days']['share']:.1%}**",
           "", "| 年 | 股票-日 | 有新闻 | 比例 |", "| --- | ---: | ---: | ---: |"]
    md += [f"| {r['year']} | {r['stock_days']:,} | {r['with_news']:,} | {r['share']:.1%} |" for r in desc["stock_days_by_year"]]
    res.mkdir(parents=True, exist_ok=True)
    (res / "news_clean_report.md").write_text("\n".join(md) + "\n")
    (res / "news_clean_stats.json").write_text(json.dumps({"stats": stats, "describe": desc, "meta": meta}, indent=2, ensure_ascii=False, default=str) + "\n")
    print("\n".join(md))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calendar-csv", default=None, help="默认 paths.raw.prices_csv/SPY.csv")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out-dir", default=None, help="把 news_clean / news_panel / meta 写到别的目录（对比实验用），默认 paths.news.*")
    args = ap.parse_args()
    paths = load_paths()
    if args.out_dir:
        out, panel_path = Path(args.out_dir) / "news_clean.parquet", Path(args.out_dir) / "news_panel.parquet"
    else:
        out, panel_path = Path(paths["news"]["clean"]), Path(paths["news"]["panel"])
    if out.exists():
        raise SystemExit(f"{out} exists; delete it first (CLAUDE.md: ask the user before overwriting /workspace/data)")
    cal_csv = Path(args.calendar_csv or Path(paths["raw"]["prices_csv"]) / "SPY.csv")
    cal = load_calendar_from_prices(cal_csv)
    membership = pl.read_parquet(Path(paths["raw"]["universe"]) / "sp500_membership.parquet")
    url_info = None
    if DATE_FIXES:
        ids = pl.read_parquet(paths["news"]["embed_candidates"], columns=["news_id"])["news_id"]
        url_info = load_url_info(paths["news"]["parquet_dir"], ids)
    df, panel, stats = build(Path(paths["news"]["embed_candidates"]), cal, membership, args.workers or ncpu(), url_info)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out, compression="zstd", row_group_size=100_000)
    panel.write_parquet(panel_path, compression="zstd")
    meta = {"out": str(out), "panel": str(panel_path), "calendar": str(cal_csv), "calendar_days": int(len(cal)),
            "calendar_range": [str(cal[0]), str(cal[-1])], "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "rules": {"cutoff_main": "09:00 ET, day precision -> 23:59:59", "cutoff_robust": "16:00 ET", "min_chars": MIN_CHARS,
                      "max_chars": MAX_CHARS, "near_dup_threshold": THRESHOLD, "near_dup_window_days": WINDOW},
            "date_fixes": DATE_FIXES, "benzinga_offset_hours": BENZINGA_OFFSET_HOURS, "scrape_stamped_range": [str(d) for d in SCRAPE_STAMPED],
            "timezone_note": "见 results/news/tz_check_conclusions.md：Benzinga 有时刻 = UTC−8，已 +8h；nasdaq.com 有时刻与 2023-11-30..12-16 剔除；nasdaq 日期取 max(FNSPID, URL)"}
    (out.parent / "news_clean_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    write_report(stats, describe(df, panel, membership, cal), meta,
                 Path(args.out_dir) if args.out_dir else ROOT / paths["results"] / "news")


if __name__ == "__main__":
    main()
