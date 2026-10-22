"""模块 2 任务 1（解析）：FNSPID 原始 CSV → 全字符串 parquet，加 news_id 与派生列。

- DuckDB 流式读取，`all_varchar=true`（列类型不一致、数值列里有俄语字符串），正规 CSV 解析器处理正文中的换行与 "" 引号；
  `max_line_size` 10 MB；`store_rejects=true` 把坏行记入 reject_errors 而不是静默丢弃，拒绝数写进报告。
- 输出每个源文件一个目录：paths.news.parquet_dir/<source>/data_*.parquet（zstd，单文件约 1 GB），完成后写 _SUCCESS；已有 _SUCCESS 跳过。
- 保留全部原始列（字符串），丢掉 nasdaq 文件多出来的索引列 `Unnamed: 0`；派生列：
  source_file, news_id（定义见 news/news_id.py）, ts_utc, has_time（时刻 != 00:00:00）, has_body（Article 非空）, url_host。
- 每个文件报告解析质量：Stock_symbol 匹配 ^[A-Z][A-Z0-9.\\-]{0,6}$ 的比例（只在非空 symbol 上算；第三方来源约 980 万行 symbol 为空，单独报 symbol_null_rate）、Url 以 http 开头的比例、Date 可解析的比例、拒绝行数。
  任一比例 < 99.5% 或拒绝行 > 0.1% 时退出码 3，由人决定是否换解析方式。

长任务：bash infra/run_bg.sh fnspid-parse python -m news.parse_fnspid [--source nasdaq_exteral_data.csv]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb

from common import ROOT, load_paths, ncpu

RAW_COLS = ["Date", "Article_title", "Stock_symbol", "Url", "Publisher", "Author", "Article",
            "Lsa_summary", "Luhn_summary", "Textrank_summary", "Lexrank_summary"]
SOURCES = {"nasdaq_exteral_data.csv": "nasdaq", "All_external.csv": "all_external"}
WS = "[ \\t\\r\\n\\f\\v]"

# 与 news/news_id.py 完全对应的 SQL 表达式（输入列名 Url、Article_title）
NORM_URL_SQL = (
    "regexp_replace(regexp_replace(regexp_replace(regexp_replace("
    f"lower(regexp_replace(coalesce(Url, ''), '^{WS}+|{WS}+$', '', 'g')),"
    " '^https?://', ''), '^www\\.', ''), '[#?].*$', ''), '/+$', '')"
)
NORM_TITLE_SQL = (
    f"regexp_replace(lower(regexp_replace(coalesce(Article_title, ''), '^{WS}+|{WS}+$', '', 'g')), "
    f"'{WS}+', ' ', 'g')"
)
NEWS_ID_SQL = f"substr(sha256({NORM_URL_SQL} || chr(10) || {NORM_TITLE_SQL}), 1, 24)"

TS_SQL = "try_strptime(trim(Date), ['%Y-%m-%d %H:%M:%S UTC', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'])"
SYMBOL_RE = "^[A-Z][A-Z0-9.\\-]{0,6}$"
THRESH_RATE, THRESH_REJECT = 0.995, 0.001


def connect(threads: int, mem_gb: int = 60, tmp: str = "/root/duckdb_tmp") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"SET threads={threads}")
    con.execute(f"SET memory_limit='{mem_gb}GB'")
    Path(tmp).mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory='{tmp}'")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET enable_progress_bar=false")   # 否则进度条会刷满 run_bg 日志
    return con


def read_csv_sql(path: str, max_line_mb: int = 10) -> str:
    return (f"read_csv('{path}', all_varchar=true, header=true, delim=',', quote='\"', escape='\"', "
            f"max_line_size={max_line_mb * 1024 * 1024}, strict_mode=false, store_rejects=true, "
            f"rejects_limit=100000, sample_size=-1)")


def select_sql(csv_sql: str, source: str) -> str:
    raw = ", ".join(f'"{c}"' for c in RAW_COLS)
    return f"""
        SELECT {raw},
               '{source}' AS source_file,
               {NEWS_ID_SQL} AS news_id,
               {TS_SQL} AS ts_utc,
               coalesce({TS_SQL}::TIME <> TIME '00:00:00', false) AS has_time,
               coalesce(length(trim(Article)) > 0, false) AS has_body,
               regexp_extract(lower(trim(coalesce(Url, ''))), '^https?://(?:www\\.)?([^/:?#]+)', 1) AS url_host
        FROM {csv_sql}
    """


def quality(con: duckdb.DuckDBPyConnection, out_dir: Path) -> dict:
    row = con.execute(f"""
        SELECT count(*) AS n_rows,
               count(DISTINCT news_id) AS n_news_id,
               avg((Stock_symbol IS NULL OR Stock_symbol = '')::INT) AS symbol_null_rate,
               avg((regexp_matches(Stock_symbol, '{SYMBOL_RE}'))::INT) FILTER (WHERE Stock_symbol IS NOT NULL AND Stock_symbol <> '') AS symbol_ok_rate,
               avg((coalesce(Url, '') LIKE 'http%')::INT) AS url_http_rate,
               avg((ts_utc IS NOT NULL)::INT) AS date_parse_rate,
               avg(has_time::INT) AS time_rate,
               avg(has_body::INT) AS body_rate,
               min(ts_utc) AS ts_min, max(ts_utc) AS ts_max
        FROM read_parquet('{out_dir}/*.parquet')
    """).fetchone()
    keys = ["n_rows", "n_news_id", "symbol_null_rate", "symbol_ok_rate", "url_http_rate", "date_parse_rate", "time_rate",
            "body_rate", "ts_min", "ts_max"]
    q = {k: (float(v) if isinstance(v, float) else (str(v) if v is not None and k.startswith("ts_") else v))
         for k, v in zip(keys, row)}
    return q


def parse_one(con: duckdb.DuckDBPyConnection, csv_path: Path, out_dir: Path, source: str) -> dict:
    t0 = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    con.execute(f"""
        COPY ({select_sql(read_csv_sql(str(csv_path)), source)})
        TO '{out_dir}' (FORMAT parquet, COMPRESSION zstd, FILE_SIZE_BYTES '1GB', ROW_GROUP_SIZE 200000)
    """)
    n_rej = con.execute("SELECT count(DISTINCT line) FROM reject_errors").fetchone()[0]
    rej_sample = con.execute(
        "SELECT line, column_name, error_type, left(error_message, 200) AS msg FROM reject_errors LIMIT 20"
    ).fetchall()
    con.execute("DELETE FROM reject_errors"); con.execute("DELETE FROM reject_scans")
    q = quality(con, out_dir)
    q.update(source_file=source, csv=str(csv_path), csv_bytes=csv_path.stat().st_size,
             n_rejected=n_rej, reject_rate=n_rej / max(q["n_rows"] + n_rej, 1),
             reject_sample=[list(map(str, r)) for r in rej_sample],
             parquet_bytes=sum(p.stat().st_size for p in out_dir.glob("*.parquet")),
             n_parquet_files=len(list(out_dir.glob("*.parquet"))), seconds=round(time.time() - t0, 1))
    q["ok"] = (min(q["symbol_ok_rate"], q["url_http_rate"], q["date_parse_rate"]) >= THRESH_RATE
               and q["reject_rate"] <= THRESH_REJECT)
    (out_dir / "_quality.json").write_text(json.dumps(q, indent=2, ensure_ascii=False) + "\n")
    (out_dir / "_SUCCESS").touch()
    return q


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=list(SOURCES), default=None, help="只处理一个文件")
    ap.add_argument("--force", action="store_true", help="忽略已有 _SUCCESS（会覆盖；按 CLAUDE.md 先问用户）")
    ap.add_argument("--requality", action="store_true", help="只在已有 parquet 上重算质量指标并更新 _quality.json")
    args = ap.parse_args()
    paths = load_paths()
    raw_dir = Path(paths["raw"]["fnspid_news"])
    pq_root = Path(paths["news"]["parquet_dir"])
    con = connect(ncpu())
    print(f"duckdb {duckdb.__version__}  threads={ncpu()}", flush=True)

    all_ok = True
    for fname, source in SOURCES.items():
        if args.source and fname != args.source:
            continue
        out_dir = pq_root / source
        if args.requality and (out_dir / "_quality.json").exists():
            old_q = json.loads((out_dir / "_quality.json").read_text())
            q = {**old_q, **quality(con, out_dir)}
            q["ok"] = (min(q["symbol_ok_rate"], q["url_http_rate"], q["date_parse_rate"]) >= THRESH_RATE
                       and q["reject_rate"] <= THRESH_REJECT)
            (out_dir / "_quality.json").write_text(json.dumps(q, indent=2, ensure_ascii=False) + "\n")
            print(json.dumps({k: v for k, v in q.items() if k != "reject_sample"}, indent=2, ensure_ascii=False), flush=True)
            all_ok &= q["ok"]
            continue
        if (out_dir / "_SUCCESS").exists() and not args.force:
            print(f"skip {source}: _SUCCESS exists", flush=True)
            continue
        print(f"== parsing {fname} -> {out_dir}", flush=True)
        q = parse_one(con, raw_dir / fname, out_dir, source)
        print(json.dumps(q, indent=2, ensure_ascii=False), flush=True)
        all_ok &= q["ok"]
    print("all ok" if all_ok else "QUALITY CHECK FAILED: see _quality.json; compare on first 200k rows before deciding")
    return 0 if all_ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
