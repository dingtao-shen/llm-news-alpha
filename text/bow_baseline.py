"""模块 3 任务 8：弱文本基线。LM 词典情绪分（无需训练）与 TF-IDF（≤ 5,000 维）+ 同一套年度滚动 Ridge。

- LM：Loughran-McDonald 主词典的 Positive / Negative 词表（paths.raw.lm_dictionary）。每篇 polarity = (正词数 − 负词数) / 词数，
  按 (feature_day, ticker) 取均值直接作为 score，写 pred_dir/lm_dict__<text>__main.parquet 与 results/ridge/lm_dict__<text>__main.json（与 Ridge 的 windows 格式一致）。
- TF-IDF：词表与 idf 只在 2015–2018 的文本上拟合（早于所有验证 / 测试期，无泄漏），sublinear tf、英文停用词、min_df 20、max_df 0.5、5,000 维；
  每篇向量按股票-日取均值，写成与嵌入聚合同格式的 agg_dir/tfidf/<text>/main/year=YYYY.parquet，再跑 models.ridge_suffstats --model tfidf。
- 文本：title，或 title + body 前 8,000 字符（与嵌入一致）；样本 = news_clean 全部行（in_sp500 标记随聚合传下去）。
运行：python -m text.bow_baseline --text-type title|body
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import polars as pl
import scipy.sparse as sp

from common import ROOT, load_paths
from models.aggregate import group_mean, write_year
from models.labels import MAIN_LABEL
from models.ridge_suffstats import TEST_YEARS, daily_ic, ic_summary

FIT_YEARS = (2015, 2018)
BODY_CHARS = 8000
TOKEN = re.compile(r"[A-Za-z]+")


# ------------------------------------------------------------------ LM 词典
def load_lm(path: Path) -> tuple[set[str], set[str]]:
    lm = pl.read_csv(path, columns=["Word", "Negative", "Positive"], infer_schema_length=0)
    pos = set(lm.filter(pl.col("Positive") != "0")["Word"].to_list())
    neg = set(lm.filter(pl.col("Negative") != "0")["Word"].to_list())
    return pos, neg


def lm_polarity(text: str, pos: set[str], neg: set[str]) -> tuple[int, int, int]:
    toks = [t.upper() for t in TOKEN.findall(text)]
    return sum(t in pos for t in toks), sum(t in neg for t in toks), len(toks)


def news_text(df: pl.DataFrame, text_type: str) -> pl.Series:
    if text_type == "title":
        return df["title"].fill_null("")
    return (df["title"].fill_null("") + "\n" + df["body"].fill_null("").str.slice(0, BODY_CHARS))


def eval_windows(pred: pl.DataFrame, labels: pl.DataFrame) -> dict:
    """与 ridge_suffstats 的 report 格式一致（只有测试指标，没有 λ）。"""
    j = pred.join(labels.select("datetime", "instrument", MAIN_LABEL), on=["datetime", "instrument"], how="inner").drop_nulls(MAIN_LABEL)
    windows = []
    for ty in TEST_YEARS:
        part = j.filter(pl.col("datetime").dt.year() == ty)
        if len(part) == 0:
            continue
        keys = part.select("datetime", "instrument")
        rank = ic_summary(daily_ic(keys, part["score"].to_numpy(), part[MAIN_LABEL].to_numpy()))
        pear = ic_summary(daily_ic(keys, part["score"].to_numpy(), part[MAIN_LABEL].to_numpy(), "pearson"))
        windows.append({"test_year": ty, "train_years": [], "val_year": None, "n_train": 0, "n_test": len(part),
                        "labels": {MAIN_LABEL: {"lambda_rel": None, "val_rank_ic": None, "test_rank_ic": round(rank["mean"], 5), "test_rank_icir": round(rank["icir"], 4),
                                                "test_ic": round(pear["mean"], 5), "test_icir": round(pear["icir"], 4), "test_days": rank["days"]}}})
    return {"windows": windows}


def run_lm(clean: pl.DataFrame, text_type: str, paths: dict) -> None:
    pos, neg = load_lm(Path(paths["raw"]["lm_dictionary"]))
    texts = news_text(clean, text_type).to_list()
    pn = np.array([lm_polarity(t, pos, neg) for t in texts], dtype=np.float64)
    polarity = np.where(pn[:, 2] > 0, (pn[:, 0] - pn[:, 1]) / np.maximum(pn[:, 2], 1), 0.0)
    df = clean.select(pl.col("feature_day").alias("datetime"), pl.col("ticker").alias("instrument"), "in_sp500").with_columns(pl.Series("score", polarity))
    agg = (df.filter(pl.col("in_sp500")).group_by("datetime", "instrument").agg(pl.col("score").mean()).sort("datetime", "instrument"))
    pred = agg.filter(pl.col("datetime").dt.year().is_in(TEST_YEARS))
    key = f"lm_dict__{text_type}__main"
    out = Path(paths["pred_dir"]); out.mkdir(parents=True, exist_ok=True)
    pred.write_parquet(out / f"{key}.parquet")
    labels = pl.read_parquet(paths["labels"])
    report = eval_windows(pred, labels)
    report.update(model="lm_dict", text_type=text_type, cutoff="main", n_pred=len(pred), lambda_rel_grid=[], n_by_year={},
                  lm_coverage={"news_with_any_lm_word": float((pn[:, 0] + pn[:, 1] > 0).mean()), "mean_words": float(pn[:, 2].mean())})
    res = ROOT / paths["results"] / "ridge"; res.mkdir(parents=True, exist_ok=True)
    (res / f"{key}.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(f"LM {text_type}: {len(pred):,} stock-days; " + "; ".join(f"{w['test_year']} RankIC {w['labels'][MAIN_LABEL]['test_rank_ic']:+.4f}" for w in report["windows"]), flush=True)


# ------------------------------------------------------------------ TF-IDF
def run_tfidf(clean: pl.DataFrame, text_type: str, paths: dict, max_features: int = 5000) -> None:
    from sklearn.feature_extraction.text import TfidfVectorizer
    texts = news_text(clean, text_type)
    years = clean["feature_day"].dt.year()
    fit_mask = (years >= FIT_YEARS[0]) & (years <= FIT_YEARS[1])
    vec = TfidfVectorizer(max_features=max_features, min_df=20, max_df=0.5, sublinear_tf=True, stop_words="english", dtype=np.float32)
    vec.fit(texts.filter(fit_mask).to_list())
    print(f"TF-IDF {text_type}: vocab {len(vec.vocabulary_)} fitted on {int(fit_mask.sum()):,} docs from {FIT_YEARS}", flush=True)
    out_dir = Path(paths["agg_dir"]) / "tfidf" / text_type / "main"; out_dir.mkdir(parents=True, exist_ok=True)
    stats = {}
    for y in sorted(set(years.to_list())):
        m = (years == y).to_numpy()
        part = clean.filter(pl.Series(m))
        X = vec.transform(news_text(part, text_type).to_list())            # 稀疏 n×V
        keys = part.select(pl.col("feature_day").alias("datetime"), pl.col("ticker").alias("instrument"),
                           (pl.col("time_precision") == "second").alias("is_timed"), "has_body", "in_sp500")
        # 用 group_mean 的分组逻辑：先按 (datetime, instrument) 排序得到组边界，再用稀疏指示矩阵求组均值
        order = np.lexsort((keys["instrument"].to_numpy(), keys["datetime"].to_numpy()))
        k = keys[order]; Xs = X[order]
        change = np.ones(len(k), dtype=bool)
        change[1:] = (k["datetime"].to_numpy()[1:] != k["datetime"].to_numpy()[:-1]) | (k["instrument"].to_numpy()[1:] != k["instrument"].to_numpy()[:-1])
        gid = np.cumsum(change) - 1
        G = sp.csr_matrix((np.ones(len(gid), dtype=np.float32), (gid, np.arange(len(gid)))), shape=(gid.max() + 1, len(gid)))
        cnt = np.asarray(G.sum(1)).ravel()
        mean = np.asarray((G @ Xs).todense()) / cnt[:, None]
        g, _ = group_mean(np.zeros((len(k), 1), dtype=np.float16), np.arange(len(k)), keys)   # 只借它算 news_cnt / n_timed / n_body / in_sp500
        write_year(out_dir / f"year={y}.parquet", g, mean.astype(np.float16))
        stats[int(y)] = {"news_rows": len(part), "stock_days": len(g)}
    (out_dir / "_meta.json").write_text(json.dumps({"model": "tfidf", "text_type": text_type, "vocab": len(vec.vocabulary_), "fit_years": list(FIT_YEARS),
                                                    "min_df": 20, "max_df": 0.5, "sublinear_tf": True, "years": stats}, indent=2) + "\n")
    print(f"TF-IDF {text_type}: aggregated {sum(v['stock_days'] for v in stats.values()):,} stock-days; running ridge", flush=True)
    subprocess.run([sys.executable, "-m", "models.ridge_suffstats", "--model", "tfidf", "--text-type", text_type, "--cutoff", "main"], check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text-type", choices=["title", "body"], required=True)
    ap.add_argument("--skip-lm", action="store_true"); ap.add_argument("--skip-tfidf", action="store_true")
    args = ap.parse_args()
    paths = load_paths()
    cols = ["news_id", "ticker", "feature_day", "time_precision", "title", "body", "has_body", "in_sp500"]
    clean = pl.read_parquet(paths["news"]["clean"], columns=cols)
    if args.text_type == "body":
        clean = clean.filter(pl.col("has_body"))
    if not args.skip_lm:
        run_lm(clean, args.text_type, paths)
    if not args.skip_tfidf:
        run_tfidf(clean, args.text_type, paths)


if __name__ == "__main__":
    main()
