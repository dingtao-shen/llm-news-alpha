"""模块 3 任务 5：股票-日聚合。同一 (feature_day, ticker) 的多篇新闻嵌入取均值，记录 news_cnt、有时刻条数、有正文条数、in_sp500。

输入：news_clean.parquet（接口文件 1）+ emb_dir/<model>/<text_type>/part-*.parquet（接口文件 2，以 news_id 为键）。
输出：agg_dir/<model>/<text_type>/<cutoff>/year=YYYY.parquet：datetime, instrument, emb(fixed_size_list<float16,H>), news_cnt, n_timed, n_body, in_sp500。
cutoff=main 用 feature_day（9:00 ET 主口径），cutoff=1600 用 feature_day_1600。
实现：把该模型该文本的全部分片读进内存（LLaMA3 标题 4.1 GB float16），按年 gather 后用 np.add.reduceat 求组均值（float32 累加）。
运行：python -m models.aggregate --model llama3_base --text-type title [--cutoff main|1600]
"""
from __future__ import annotations

import argparse
import glob
import json
import time
from pathlib import Path

import numpy as np
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from common import load_paths


def load_embeddings(emb_dir: Path) -> tuple[pl.DataFrame, np.ndarray]:
    files = sorted(glob.glob(str(emb_dir / "part-*.parquet")))
    assert files, f"no shards in {emb_dir}"
    ids, mats = [], []
    for f in files:
        t = pq.read_table(f)
        ids.extend(t["news_id"].to_pylist())
        mats.append(np.stack(t["emb"].to_numpy(zero_copy_only=False)))
    emb = np.concatenate(mats)
    return pl.DataFrame({"news_id": ids, "row": np.arange(len(ids), dtype=np.int64)}), emb


def group_mean(emb: np.ndarray, rows: np.ndarray, keys: pl.DataFrame) -> tuple[pl.DataFrame, np.ndarray]:
    """keys 与 rows 同长；按 (datetime, instrument) 分组求均值。返回 (组键与计数, 均值矩阵 float16)。"""
    order = np.lexsort((keys["instrument"].to_numpy(), keys["datetime"].to_numpy()))
    k = keys[order]; r = rows[order]
    change = np.ones(len(k), dtype=bool)
    change[1:] = (k["datetime"].to_numpy()[1:] != k["datetime"].to_numpy()[:-1]) | (k["instrument"].to_numpy()[1:] != k["instrument"].to_numpy()[:-1])
    starts = np.flatnonzero(change)
    x = emb[r].astype(np.float32)
    sums = np.add.reduceat(x, starts, axis=0)
    cnt = np.diff(np.append(starts, len(k)))
    mean = (sums / cnt[:, None]).astype(np.float16)
    g = k[starts].with_columns(pl.Series("news_cnt", cnt.astype(np.int32)))
    for col in ("is_timed", "has_body", "in_sp500"):
        v = k[col].to_numpy().astype(np.int32)
        g = g.with_columns(pl.Series({"is_timed": "n_timed", "has_body": "n_body", "in_sp500": "n_in"}[col], np.add.reduceat(v, starts)))
    g = g.with_columns((pl.col("n_in") > 0).alias("in_sp500")).drop("n_in", "is_timed", "has_body")
    return g, mean


def write_year(path: Path, g: pl.DataFrame, mean: np.ndarray) -> None:
    flat = pa.array(mean.reshape(-1))
    col = pa.FixedSizeListArray.from_arrays(flat, mean.shape[1])
    table = pa.table({"datetime": pa.array(g["datetime"].to_list(), pa.date32()), "instrument": pa.array(g["instrument"].to_list(), pa.string()),
                      "emb": col, "news_cnt": pa.array(g["news_cnt"].to_list(), pa.int32()), "n_timed": pa.array(g["n_timed"].to_list(), pa.int32()),
                      "n_body": pa.array(g["n_body"].to_list(), pa.int32()), "in_sp500": pa.array(g["in_sp500"].to_list(), pa.bool_())})
    tmp = path.with_suffix(".parquet.tmp")
    pq.write_table(table, tmp, compression="zstd")
    tmp.replace(path)


def aggregate(clean: pl.DataFrame, emb_ids: pl.DataFrame, emb: np.ndarray, out_dir: Path, day_col: str) -> dict:
    df = (clean.select("news_id", "ticker", pl.col(day_col).alias("datetime"), (pl.col("time_precision") == "second").alias("is_timed"), "has_body", "in_sp500")
               .join(emb_ids, on="news_id", how="inner").rename({"ticker": "instrument"}))
    missing = len(clean) - len(df)
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = {"clean_rows": len(clean), "rows_without_embedding": missing, "years": {}}
    for (year,), part in df.group_by(pl.col("datetime").dt.year(), maintain_order=True):
        g, mean = group_mean(emb, part["row"].to_numpy(), part.select("datetime", "instrument", "is_timed", "has_body", "in_sp500"))
        write_year(out_dir / f"year={year}.parquet", g, mean)
        stats["years"][int(year)] = {"news_rows": len(part), "stock_days": len(g), "stock_days_in_sp500": int(g["in_sp500"].sum()),
                                     "mean_news_per_day": round(float(g["news_cnt"].mean()), 3)}
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3_base")
    ap.add_argument("--text-type", choices=["title", "body"], required=True)
    ap.add_argument("--cutoff", choices=["main", "1600"], default="main")
    args = ap.parse_args()
    paths = load_paths()
    t0 = time.time()
    emb_ids, emb = load_embeddings(Path(paths["emb_dir"]) / args.model / args.text_type)
    print(f"embeddings: {emb.shape} loaded in {time.time() - t0:.1f}s", flush=True)
    clean = pl.read_parquet(paths["news"]["clean"], columns=["news_id", "ticker", "feature_day", "feature_day_1600", "time_precision", "has_body", "in_sp500"])
    out_dir = Path(paths["agg_dir"]) / args.model / args.text_type / args.cutoff
    stats = aggregate(clean, emb_ids, emb, out_dir, "feature_day" if args.cutoff == "main" else "feature_day_1600")
    stats.update(model=args.model, text_type=args.text_type, cutoff=args.cutoff, hidden=int(emb.shape[1]), secs=round(time.time() - t0, 1))
    (out_dir / "_meta.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
