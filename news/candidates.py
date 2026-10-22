"""嵌入候选集：只用成本低的规则过滤，写出 paths.news.embed_candidates（按 news_id 排序，行组 = 嵌入分片大小）。

规则（顺序固定，各步剔除数写进报告）：
 1. 日期：ts_utc 可解析且 date(ts_utc) >= 2014-12-31（样本从 2015 起，往前留一天余量，因为时区还没校验）；
 2. 语言：标题含西里尔字母（\\p{Cyrillic}）或域名以 lenta.ru 结尾的剔除（俄语 Lenta 记录）；
 3. 标题：规范化后非空；
 4. ticker：upper(trim(Stock_symbol)) 把 '-' 视为 '.' 后在 2015–2023 时点成分股全集中（results/universe/sp500_tickers_2015_2023.txt）；
 5. 单一股票：在**过滤前的全量数据**上，同一 news_id 出现在 >1 个不同 Stock_symbol 下的整篇剔除（原文规则）；
 6. 去重：同一 news_id 多行（同一 ticker 下重复）时保留 has_body 为真、正文更长的那一行。
输入只用 nasdaq 文件：模块 2 统计证实 All_external 的 11,551,494 个 news_id 全部在 nasdaq 文件中且 ticker、行数、日期、正文标记完全相同。
输出列：news_id, ticker（成分股表写法）, ts_utc, has_time, title, body, has_body, source_file。
嵌入分片按行号切（第 i 片 = 行 [i*SHARD, (i+1)*SHARD)），所以文件必须按 news_id 排序且行组大小 = SHARD。
news_id 是哈希，按它排序等于随机打乱：每个已完成分片都是候选集的随机样本。

运行：make news-candidates（几分钟，前台可跑）。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import duckdb
import polars as pl

from common import ROOT, load_paths, ncpu
from news.parse_fnspid import NORM_TITLE_SQL, connect

SHARD = 50_000
MIN_DATE = "2014-12-31"
TOKENS_PER_SEC = 11_144  # 模块 0 实测 LLaMA3-8B 32 × 512


def load_universe(path: Path) -> dict[str, str]:
    """{规范化代码('-'→'.') : 成分股表写法}"""
    tickers = [t.strip() for t in path.read_text().splitlines() if t.strip()]
    return {t.replace("-", "."): t for t in tickers}


def build_candidates(con: duckdb.DuckDBPyConnection, parquet_glob: str, universe: dict[str, str],
                     out_path: Path) -> dict:
    con.execute("CREATE OR REPLACE TEMP TABLE universe AS SELECT * FROM (VALUES "
                + ",".join("(?, ?)" for _ in universe) + ") t(sym_norm, ticker)",
                [x for kv in universe.items() for x in kv])
    con.execute(f"CREATE OR REPLACE VIEW n AS SELECT * FROM read_parquet('{parquet_glob}')")
    con.execute("""
        CREATE OR REPLACE TEMP TABLE multi AS
        SELECT news_id, count(DISTINCT upper(trim(Stock_symbol))) AS n_sym, count(*) AS n_rows
        FROM n GROUP BY news_id HAVING n_sym > 1""")
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE flagged AS
        SELECT n.*, replace(upper(trim(coalesce(Stock_symbol, ''))), '-', '.') AS sym_norm,
               {NORM_TITLE_SQL} AS norm_title,
               (ts_utc IS NOT NULL AND ts_utc >= TIMESTAMP '{MIN_DATE}') AS f_date,
               NOT (regexp_matches(coalesce(Article_title, ''), '\\p{{Cyrillic}}')
                    OR coalesce(url_host, '') LIKE '%lenta.ru') AS f_lang,
               ({NORM_TITLE_SQL}) <> '' AS f_title,
               (replace(upper(trim(coalesce(Stock_symbol, ''))), '-', '.') IN (SELECT sym_norm FROM universe)) AS f_ticker,
               (news_id NOT IN (SELECT news_id FROM multi)) AS f_single
        FROM n""")
    funnel_row = con.execute("""
        SELECT count(*), sum(f_date::INT), sum((f_date AND f_lang)::INT), sum((f_date AND f_lang AND f_title)::INT),
               sum((f_date AND f_lang AND f_title AND f_ticker)::INT),
               sum((f_date AND f_lang AND f_title AND f_ticker AND f_single)::INT)
        FROM flagged""").fetchone()
    names = ["raw_rows", "after_date", "after_lang", "after_title", "after_ticker", "after_single"]
    funnel = dict(zip(names, map(int, funnel_row)))

    single_by = con.execute("""
        SELECT source_file, year(ts_utc) AS year, count(*) AS rows_removed, count(DISTINCT news_id) AS articles_removed
        FROM flagged WHERE f_date AND f_lang AND f_title AND f_ticker AND NOT f_single
        GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()
    unmatched = con.execute("""
        SELECT sym_norm, count(*) AS n FROM flagged WHERE f_date AND f_lang AND f_title AND NOT f_ticker
        GROUP BY 1 ORDER BY n DESC LIMIT 20""").fetchall()
    n_matched_syms = con.execute(
        "SELECT count(DISTINCT sym_norm) FROM flagged WHERE f_date AND f_lang AND f_title AND f_ticker").fetchone()[0]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"""
        COPY (
          SELECT news_id, u.ticker, ts_utc, has_time, trim(Article_title) AS title,
                 CASE WHEN has_body THEN Article END AS body, has_body, source_file
          FROM (SELECT *, row_number() OVER (PARTITION BY news_id
                                             ORDER BY has_body DESC, length(Article) DESC NULLS LAST, source_file) AS rn
                FROM flagged WHERE f_date AND f_lang AND f_title AND f_ticker AND f_single) f
          JOIN universe u USING (sym_norm)
          WHERE rn = 1
          ORDER BY news_id
        ) TO '{out_path}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE {SHARD})""")

    ids = pl.scan_parquet(str(out_path)).select("news_id", "has_body", pl.col("ts_utc").dt.year().alias("year")).collect()
    assert ids["news_id"].is_sorted() and ids["news_id"].n_unique() == len(ids), "news_id must be sorted and unique"
    by_year = ids.group_by("year").agg(pl.len().alias("n"), pl.col("has_body").sum().alias("n_body")).sort("year")
    stats = {
        "n_candidates": len(ids), "n_with_body": int(ids["has_body"].sum()), "funnel": funnel,
        "dedup_removed": funnel["after_single"] - len(ids),
        "single_stock_removed_by_source_year": [dict(zip(["source_file", "year", "rows_removed", "articles_removed"], r)) for r in single_by],
        "single_stock_removed_total": {"rows": funnel["after_ticker"] - funnel["after_single"],
                                       "articles": int(con.execute("SELECT count(DISTINCT news_id) FROM flagged WHERE f_date AND f_lang AND f_title AND f_ticker AND NOT f_single").fetchone()[0])},
        "unmatched_tickers_top20": [{"symbol": s, "rows": int(n)} for s, n in unmatched],
        "n_matched_symbols": int(n_matched_syms), "n_universe": len(universe),
        "by_year": by_year.to_dicts(), "shard": SHARD, "min_date": MIN_DATE, "out": str(out_path),
    }
    return stats


def token_estimate(out_path: Path, model_id: str, n_sample: int = 20_000, seed: int = 0) -> dict:
    """抽样统计 LLaMA3 分词后的 token 数，换算 GPU 小时（按模块 0 实测吞吐，含 10% padding 余量）。"""
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_id)
    lf = pl.scan_parquet(str(out_path))
    n_all = lf.select(pl.len()).collect().item()
    n_body = lf.filter(pl.col("has_body")).select(pl.len()).collect().item()
    s = lf.select("title", "body", "has_body").collect().sample(min(n_sample, n_all), seed=seed)
    t_title = [len(x) for x in tok(s["title"].to_list(), add_special_tokens=True)["input_ids"]]
    sb = s.filter(pl.col("has_body"))
    t_body = [min(512, len(x)) for x in tok([f"{a}\n{b}" for a, b in zip(sb["title"], sb["body"])],
                                            add_special_tokens=True, truncation=True, max_length=512)["input_ids"]]
    mean_t, mean_b = sum(t_title) / len(t_title), (sum(t_body) / len(t_body) if t_body else 0.0)
    hours = lambda n, m: n * m / TOKENS_PER_SEC / 3600 * 1.1
    return {"sample": len(s), "title_tokens_mean": round(mean_t, 1), "title_tokens_max": max(t_title),
            "body_tokens_mean_capped512": round(mean_b, 1),
            "body_share_hitting_512": round(sum(t >= 512 for t in t_body) / max(len(t_body), 1), 3),
            "title_gpu_hours": round(hours(n_all, mean_t), 2), "body_gpu_hours": round(hours(n_body, mean_b), 2),
            "tokens_per_sec_assumed": TOKENS_PER_SEC}


def write_report(stats: dict, est: dict | None, res: Path) -> None:
    f = stats["funnel"]
    md = ["# 嵌入候选集", "",
          f"- 候选 **{stats['n_candidates']:,}** 条，其中有正文 **{stats['n_with_body']:,}** 条；输出 `{stats['out']}`（按 news_id 排序，行组 {stats['shard']:,}）", "",
          "## 过滤漏斗", "", "| 步骤 | 剩余行数 | 剔除 |", "| --- | ---: | ---: |",
          f"| 原始行 | {f['raw_rows']:,} | |",
          f"| 日期可解析且 ≥ {stats['min_date']} | {f['after_date']:,} | {f['raw_rows'] - f['after_date']:,} |",
          f"| 剔除俄语 | {f['after_lang']:,} | {f['after_date'] - f['after_lang']:,} |",
          f"| 标题非空 | {f['after_title']:,} | {f['after_lang'] - f['after_title']:,} |",
          f"| ticker 在 2015–2023 成分股全集（{stats['n_matched_symbols']} / {stats['n_universe']} 个代码有新闻） | {f['after_ticker']:,} | {f['after_title'] - f['after_ticker']:,} |",
          f"| 单一股票（整篇剔除） | {f['after_single']:,} | {f['after_ticker'] - f['after_single']:,} 行 / {stats['single_stock_removed_total']['articles']:,} 篇 |",
          f"| 同一 news_id 去重（保留带正文的） | {stats['n_candidates']:,} | {stats['dedup_removed']:,} |", "",
          "## 单一股票规则剔除，按 source_file × 年份", "", "| source_file | 年 | 剔除行数 | 剔除文章数 |", "| --- | ---: | ---: | ---: |"]
    md += [f"| {r['source_file']} | {r['year']} | {r['rows_removed']:,} | {r['articles_removed']:,} |" for r in stats["single_stock_removed_by_source_year"]]
    md += ["", "## 未匹配成分股全集的 ticker（前 20，通过日期/语言/标题过滤后）", "", "| symbol | 行数 |", "| --- | ---: |"]
    md += [f"| {r['symbol']} | {r['rows']:,} |" for r in stats["unmatched_tickers_top20"]]
    md += ["", "## 候选集按年", "", "| 年 | 条数 | 有正文 |", "| --- | ---: | ---: |"]
    md += [f"| {r['year']} | {r['n']:,} | {r['n_body']:,} |" for r in stats["by_year"]]
    if est:
        md += ["", "## GPU 时间估算（LLaMA3-8B，按模块 0 实测 11,144 tokens/s，+10% padding）", "",
               f"- 抽样 {est['sample']:,} 条：标题平均 {est['title_tokens_mean']} token（最长 {est['title_tokens_max']}）；"
               f"标题+正文截到 512 后平均 {est['body_tokens_mean_capped512']} token，{est['body_share_hitting_512']:.0%} 的正文记录触顶 512",
               f"- 标题全集 ≈ **{est['title_gpu_hours']} GPU 小时**；原文子集 ≈ **{est['body_gpu_hours']} GPU 小时**"]
    res.mkdir(parents=True, exist_ok=True)
    (res / "embed_candidates_report.md").write_text("\n".join(md) + "\n")
    (res / "embed_candidates_stats.json").write_text(json.dumps({"stats": stats, "token_estimate": est}, indent=2, ensure_ascii=False) + "\n")
    print("\n".join(md))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-token-estimate", action="store_true")
    args = ap.parse_args()
    paths = load_paths()
    out = Path(paths["news"]["embed_candidates"])
    if out.exists():
        raise SystemExit(f"{out} exists; delete it first (CLAUDE.md: ask the user before overwriting /workspace/data)")
    con = connect(ncpu())
    universe = load_universe(ROOT / paths["results"] / "universe" / "sp500_tickers_2015_2023.txt")
    stats = build_candidates(con, f"{paths['news']['parquet_dir']}/nasdaq/*.parquet", universe, out)
    est = None if args.no_token_estimate else token_estimate(out, paths["models"]["llama3_base"])
    (out.parent / (out.stem + "_meta.json")).write_text(json.dumps({"stats": stats, "token_estimate": est}, indent=2, ensure_ascii=False) + "\n")
    write_report(stats, est, ROOT / paths["results"] / "news")


if __name__ == "__main__":
    main()
