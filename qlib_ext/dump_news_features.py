"""模块 4 任务 1（方式 A）：把 PCA-64 新闻特征与价格合并成每只一个 CSV，重新 dump 成一套独立的 Qlib 二进制（paths.qlib_news_dir）。

- 字段：open, high, low, close, volume, factor, adj_close +
  pct_0..pct_63（LLaMA3 标题 PCA-64）、news_cnt_t、has_news_t；pcb_0..pcb_63（LLaMA3 原文 PCA-64）、news_cnt_b、has_news_b。
  没有新闻的股票-日新闻特征填 0、has_news=0（模型靠 has_news 区分"中性新闻"和"没有新闻"）。
- 新闻特征按 feature_day 对齐到价格日期（特征日 t 的新闻 → t 行），与标签 Ref($open,-2)/Ref($open,-1)-1 的口径一致。
- 价格数据集 /workspace/qlib_data/us_sp500 保持冻结；instruments/sp500.txt 复制过去。
运行：python -m qlib_ext.dump_news_features [--model llama3_base]（约 5 分钟）
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

from common import load_paths, ncpu

K = 64


def load_pca(pca_dir: Path, prefix: str) -> pl.DataFrame:
    files = sorted(pca_dir.glob("year=*.parquet"))
    df = pl.concat([pl.read_parquet(f, columns=["datetime", "instrument", "news_cnt"] + [f"pc_{i}" for i in range(K)]) for f in files])
    return df.rename({f"pc_{i}": f"{prefix}_{i}" for i in range(K)} | {"news_cnt": f"news_cnt_{prefix[-1]}"}).with_columns(pl.lit(1).alias(f"has_news_{prefix[-1]}"))


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default="llama3_base"); ap.add_argument("--cutoff", default="main")
    args = ap.parse_args()
    paths = load_paths()
    t0 = time.time()
    prices_dir = Path(paths["raw"]["prices_csv"]); csv_dir = Path(paths["qlib_news_csv"]); qdir = Path(paths["qlib_news_dir"])
    if csv_dir.exists():
        shutil.rmtree(csv_dir)
    csv_dir.mkdir(parents=True)
    pca_root = Path(paths["pca_dir"]) / args.model
    news = load_pca(pca_root / "title" / args.cutoff, "pct").join(load_pca(pca_root / "body" / args.cutoff, "pcb"), on=["datetime", "instrument"], how="full", coalesce=True)
    news = news.with_columns(pl.col("datetime").cast(pl.Date))
    feat_cols = [c for c in news.columns if c not in ("datetime", "instrument")]
    print(f"news features: {len(news):,} stock-days, {len(feat_cols)} columns", flush=True)
    n_written = 0
    for f in sorted(prices_dir.glob("*.csv")):
        px = pl.read_csv(f, schema_overrides={"date": pl.Utf8}).with_columns(pl.col("date").str.to_date().alias("datetime"))
        sub = news.filter(pl.col("instrument") == f.stem).drop("instrument")
        out = px.join(sub, on="datetime", how="left").drop("datetime")
        out = out.with_columns([pl.col(c).fill_null(0.0) for c in feat_cols])
        out.write_csv(csv_dir / f.name, float_precision=6)
        n_written += 1
    print(f"wrote {n_written} CSVs to {csv_dir} in {time.time() - t0:.0f}s; dumping to {qdir}", flush=True)
    if qdir.exists():
        shutil.rmtree(qdir)
    fields = "open,high,low,close,volume,factor,adj_close," + ",".join(feat_cols)
    subprocess.run([sys.executable, "/workspace/src/qlib/scripts/dump_bin.py", "dump_all", "--data_path", str(csv_dir), "--qlib_dir", str(qdir),
                    "--include_fields", fields, "--date_field_name", "date", "--symbol_field_name", "symbol", "--max_workers", str(ncpu())], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.copy(Path(paths["qlib_dir"]) / "instruments" / "sp500.txt", qdir / "instruments" / "sp500.txt")
    print(f"done in {time.time() - t0:.0f}s: {qdir} ({len(list((qdir / 'features').iterdir()))} instruments, {len(fields.split(','))} fields)", flush=True)


if __name__ == "__main__":
    main()
