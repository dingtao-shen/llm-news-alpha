"""模块 2 任务 2：来源 × 年份 × 时刻可用率 × 正文可用率 统计表。

读 paths.news.parquet_dir 下两个源的 parquet，写 results/news/：
- fnspid_source_stats.csv         source_file × url_host × year
- fnspid_source_stats_by_year.csv source_file × year（含 symbol/url/date 质量比例）
- fnspid_parse_report.md          总览：行数、拒绝行、日期失败、唯一 news_id、两文件 news_id 重叠、各文件质量指标
运行：make news-stats（几分钟，可前台）
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from common import ROOT, load_paths, ncpu
from news.parse_fnspid import SYMBOL_RE, connect


def main() -> None:
    paths = load_paths()
    pq = Path(paths["news"]["parquet_dir"])
    res = ROOT / paths["results"] / "news"; res.mkdir(parents=True, exist_ok=True)
    con = connect(ncpu())
    con.execute(f"CREATE VIEW n AS SELECT * FROM read_parquet('{pq}/*/*.parquet', hive_partitioning=false)")

    con.execute(f"""
        COPY (SELECT source_file, coalesce(url_host, '') AS url_host, year(ts_utc) AS year,
                     count(*) AS n_rows, count(DISTINCT news_id) AS n_news_id,
                     round(avg(has_time::INT), 4) AS time_rate, round(avg(has_body::INT), 4) AS body_rate
              FROM n GROUP BY 1, 2, 3 ORDER BY 1, 2, 3)
        TO '{res / "fnspid_source_stats.csv"}' (FORMAT csv, HEADER)""")
    con.execute(f"""
        COPY (SELECT source_file, year(ts_utc) AS year, count(*) AS n_rows, count(DISTINCT news_id) AS n_news_id,
                     count(DISTINCT Stock_symbol) AS n_symbols,
                     round(avg(has_time::INT), 4) AS time_rate, round(avg(has_body::INT), 4) AS body_rate,
                     round(avg((Stock_symbol IS NULL OR Stock_symbol = '')::INT), 4) AS symbol_null_rate,
                     round(avg((regexp_matches(Stock_symbol, '{SYMBOL_RE}'))::INT) FILTER (WHERE Stock_symbol IS NOT NULL AND Stock_symbol <> ''), 4) AS symbol_ok_rate,
                     round(avg((coalesce(Url, '') LIKE 'http%')::INT), 4) AS url_http_rate,
                     round(avg((ts_utc IS NOT NULL)::INT), 4) AS date_parse_rate
              FROM n GROUP BY 1, 2 ORDER BY 1, 2)
        TO '{res / "fnspid_source_stats_by_year.csv"}' (FORMAT csv, HEADER)""")

    tot = con.execute("""
        SELECT count(*), count(DISTINCT news_id), sum((ts_utc IS NULL)::INT),
               sum(has_time::INT), sum(has_body::INT), min(ts_utc), max(ts_utc) FROM n""").fetchone()
    overlap = con.execute("""
        SELECT count(*) FROM (SELECT news_id FROM n GROUP BY news_id HAVING count(DISTINCT source_file) > 1)""").fetchone()[0]
    per_src = con.execute("""
        SELECT source_file, count(*), count(DISTINCT news_id), round(avg(has_time::INT), 4), round(avg(has_body::INT), 4)
        FROM n GROUP BY 1 ORDER BY 1""").fetchall()
    top_hosts = con.execute("""
        SELECT source_file, url_host, count(*) AS cnt, round(avg(has_time::INT), 3), round(avg(has_body::INT), 3),
               round(avg((Stock_symbol IS NULL OR Stock_symbol = '')::INT), 3) AS symbol_null_rate
        FROM n GROUP BY 1, 2 QUALIFY row_number() OVER (PARTITION BY source_file ORDER BY cnt DESC) <= 10 ORDER BY 1, 3 DESC""").fetchall()
    quals = {d.name: json.loads((d / "_quality.json").read_text()) for d in sorted(pq.iterdir()) if (d / "_quality.json").exists()}

    md = ["# FNSPID 解析与来源统计", "",
          f"- 总行数 {tot[0]:,}；唯一 news_id {tot[1]:,}；日期解析失败 {tot[2]:,}；有时刻 {tot[3]:,}（{tot[3] / tot[0]:.1%}）；有正文 {tot[4]:,}（{tot[4] / tot[0]:.1%}）",
          f"- 时间范围 {tot[5]} 至 {tot[6]}；两文件共有的 news_id {overlap:,}", "",
          "| source_file | 行数 | 唯一 news_id | 时刻可用率 | 正文可用率 | 拒绝行 | symbol_ok | url_http | date_parse | 耗时 s |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for s, n, nid, tr, br in per_src:
        q = quals.get(s, {})
        md.append(f"| {s} | {n:,} | {nid:,} | {tr:.1%} | {br:.1%} | {q.get('n_rejected', '?')} | "
                  f"{q.get('symbol_ok_rate', 0):.4%} | {q.get('url_http_rate', 0):.4%} | {q.get('date_parse_rate', 0):.4%} | {q.get('seconds', '?')} |")
    md += ["", "## 各文件行数最多的域名", "", "| source_file | url_host | 行数 | 时刻可用率 | 正文可用率 | symbol 为空 |", "| --- | --- | ---: | ---: | ---: | ---: |"]
    md += [f"| {s} | {h} | {n:,} | {tr:.1%} | {br:.1%} | {sn:.1%} |" for s, h, n, tr, br, sn in top_hosts]
    sym = con.execute("""
        SELECT source_file, sum((Stock_symbol IS NOT NULL AND Stock_symbol <> '')::INT) AS n_sym,
               sum((Stock_symbol IS NOT NULL AND Stock_symbol <> '' AND has_time)::INT) AS n_sym_time,
               sum((Stock_symbol IS NOT NULL AND Stock_symbol <> '' AND has_body)::INT) AS n_sym_body,
               sum((Stock_symbol IS NOT NULL AND Stock_symbol <> '' AND ts_utc >= TIMESTAMP '2015-01-01')::INT) AS n_sym_2015
        FROM n GROUP BY 1 ORDER BY 1""").fetchall()
    md += ["", "## 带 ticker 的行（能用于个股预测的部分）", "", "| source_file | 带 ticker | 其中有时刻 | 其中有正文 | 其中 2015 年起 |", "| --- | ---: | ---: | ---: | ---: |"]
    md += [f"| {s} | {a:,} | {b:,} ({b / a:.1%}) | {c:,} ({c / a:.1%}) | {d:,} |" for s, a, b, c, d in sym]
    md += ["", "明细见 `fnspid_source_stats.csv`（source × host × year）与 `fnspid_source_stats_by_year.csv`。",
           "news_id 定义见 `news/news_id.py`。"]
    (res / "fnspid_parse_report.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
