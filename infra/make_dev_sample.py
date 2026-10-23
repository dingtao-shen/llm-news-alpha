"""把一份约 100 MB 的开发样本写到 /workspace/data/dev_sample/ 并打包成 dev_sample.tgz，供 Mac 的 dev_data/ 使用。

内容（都是卷上真实产物的子集，不进 git）：
- fnspid_sample.parquet        nasdaq 文件 parquet 随机 15,000 行 + 1,000 篇多 ticker 文章的全部行（保留单一股票规则的测试场景），全部列
- embed_candidates_sample.parquet  标准新闻表前 5,000 行（按 news_id 哈希排序，前 N 行就是随机样本）
- news_clean_sample.parquet        对应的 news_clean 行（接口文件 1）
- emb/llama3_base/title/part-00000.parquet   与上面 5,000 行一一对应的标题嵌入
- emb/llama3_base/body/part-00000.parquet    其中有正文的记录的原文嵌入
- emb/llama3_base/{title,body}/_meta.json    原样拷贝
- universe/instruments_sp500.txt、universe/sp500_membership.parquet
- tz_check_urls.csv             时区 / 日期校验抽样：有时刻 × 仅日期 × Benzinga × nasdaq.com 各 100 条
- _manifest.json、README.md
运行：make dev-sample（Pod，几分钟）。Mac 上：rsync runpod:/workspace/data/dev_sample.tgz . && tar xzf dev_sample.tgz -C dev_data --strip-components=1
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from pathlib import Path

import duckdb
import polars as pl
import pyarrow.parquet as pq

from common import ROOT, load_paths, ncpu

SEED = 0
N_RANDOM, N_MULTI, N_CAND, N_TZ = 15_000, 1_000, 5_000, 100


def main() -> None:
    paths = load_paths()
    out = Path(paths["workspace"]) / "data" / "dev_sample"
    if out.exists():
        shutil.rmtree(out)
    (out / "emb" / "llama3_base" / "title").mkdir(parents=True)
    (out / "emb" / "llama3_base" / "body").mkdir(parents=True)
    (out / "universe").mkdir()
    con = duckdb.connect()
    con.execute(f"SET threads={ncpu()}"); con.execute("SET memory_limit='40GB'"); con.execute("SET enable_progress_bar=false")
    manifest: dict = {"created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "seed": SEED,
                      "code_commit": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()}

    # 1. FNSPID 样本：随机行 + 完整的多 ticker 文章
    pq_glob = f"{paths['news']['parquet_dir']}/nasdaq/*.parquet"
    con.execute(f"CREATE VIEW n AS SELECT * FROM read_parquet('{pq_glob}')")
    con.execute(f"""
        CREATE TABLE multi_ids AS
        SELECT news_id FROM (SELECT news_id, count(DISTINCT Stock_symbol) k FROM n
                             WHERE Stock_symbol IS NOT NULL AND ts_utc >= TIMESTAMP '2015-01-01' GROUP BY 1 HAVING k BETWEEN 2 AND 6)
        USING SAMPLE reservoir({N_MULTI} ROWS) REPEATABLE ({SEED})""")
    con.execute(f"""
        COPY (SELECT * FROM (SELECT * FROM n USING SAMPLE reservoir({N_RANDOM} ROWS) REPEATABLE ({SEED}))
              UNION ALL
              SELECT * FROM n WHERE news_id IN (SELECT news_id FROM multi_ids))
        TO '{out / "fnspid_sample.parquet"}' (FORMAT parquet, COMPRESSION zstd)""")
    manifest["fnspid_sample_rows"] = con.execute(f"SELECT count(*) FROM '{out / 'fnspid_sample.parquet'}'").fetchone()[0]

    # 2. 候选集前 N 行 + 对应嵌入
    cand = pl.scan_parquet(paths["news"]["embed_candidates"]).head(N_CAND).collect()
    cand.write_parquet(out / "embed_candidates_sample.parquet")
    ids = set(cand["news_id"].to_list())
    emb_root = Path(paths["emb_dir"]) / "llama3_base"
    for tt in ("title", "body"):
        t = pq.ParquetFile(emb_root / tt / "part-00000.parquet").read_row_group(0)
        tbl = pl.from_arrow(t).filter(pl.col("news_id").is_in(ids))
        expected = len(ids) if tt == "title" else int(cand["has_body"].sum())
        assert len(tbl) == expected, (tt, len(tbl), expected)
        assert tbl["news_id"].is_sorted()
        tbl.write_parquet(out / "emb" / "llama3_base" / tt / "part-00000.parquet")
        shutil.copy(emb_root / tt / "_meta.json", out / "emb" / "llama3_base" / tt / "_meta.json")
        manifest[f"emb_{tt}_rows"] = len(tbl)
    manifest["candidates_rows"] = len(cand)
    clean = pl.scan_parquet(paths["news"]["clean"]).filter(pl.col("news_id").is_in(list(ids))).collect()
    clean.write_parquet(out / "news_clean_sample.parquet")
    manifest["news_clean_rows"] = len(clean)

    # 3. 股票池
    shutil.copy(Path(paths["qlib_dir"]) / "instruments" / "sp500.txt", out / "universe" / "instruments_sp500.txt")
    shutil.copy(Path(paths["raw"]["universe"]) / "sp500_membership.parquet", out / "universe" / "sp500_membership.parquet")

    # 4. 时区 / 日期校验抽样
    con.execute(f"""
        COPY (
          SELECT news_id, Date, ts_utc, has_time, url_host, Stock_symbol, Article_title, Url FROM (
            SELECT *, row_number() OVER (PARTITION BY has_time, url_host ORDER BY hash(news_id || '{SEED}')) AS rn
            FROM n WHERE Stock_symbol IS NOT NULL AND ts_utc >= TIMESTAMP '2015-01-01'
              AND url_host IN ('benzinga.com', 'nasdaq.com') AND Url LIKE 'http%')
          WHERE rn <= {N_TZ} ORDER BY has_time DESC, url_host, rn
        ) TO '{out / "tz_check_urls.csv"}' (FORMAT csv, HEADER)""")
    manifest["tz_check_rows"] = con.execute(f"SELECT has_time, url_host, count(*) FROM '{out / 'tz_check_urls.csv'}' GROUP BY 1, 2 ORDER BY 1, 2").fetchall()

    (out / "README.md").write_text(__doc__)
    (out / "_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str) + "\n")
    tgz = out.parent / "dev_sample.tgz"
    subprocess.check_call(["tar", "czf", str(tgz), "-C", str(out.parent), out.name])
    print(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
    print(f"wrote {tgz} ({tgz.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
