"""模块 3 任务 7：PCA 只在 2015–2018 的股票-日聚合嵌入上拟合一次，导出 256 维（MLP / 随机森林）与 64 维（Qlib）特征。

- 拟合期早于所有验证期与测试期（最早的验证年是 2019），对每个滚动窗口都没有泄漏；均值与主成分只用拟合期。
- 输入：agg_dir/<model>/<text_type>/<cutoff>/year=YYYY.parquet（in_sp500 行）；输出：pca_dir/<model>/<text_type>/<cutoff>/{pca_model.npz, year=YYYY.parquet}
  （datetime, instrument, pc_0..pc_{k-1} float32 的两套列：pc256_*、pc64_* 用同一组主成分，64 维就是前 64 个）。
- 诊断：累计解释方差（64 / 256 维）、第一主成分与标题 / 正文长度、news_cnt 的相关（检查 PC1 是否只在度量文本长度）。
运行：python -m models.pca_export --model llama3_base --text-type body [--cutoff main]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from common import ROOT, load_paths

FIT_YEARS = (2015, 2018)
K_MAX = 256


def load_year(agg_dir: Path, year: int, only_sp500: bool = True) -> tuple[pl.DataFrame, np.ndarray]:
    t = pq.read_table(agg_dir / f"year={year}.parquet")
    keys = pl.from_arrow(t.select(["datetime", "instrument", "news_cnt", "n_body", "in_sp500"]))
    emb = np.stack(t["emb"].to_numpy(zero_copy_only=False)).astype(np.float32)
    if only_sp500:
        m = keys["in_sp500"].to_numpy(); keys, emb = keys.filter(pl.col("in_sp500")), emb[m]
    return keys, emb


def fit_pca(X: np.ndarray, k: int = K_MAX, seed: int = 0) -> dict:
    """中心化后做截断 SVD（随机化），返回 mean、components(k×P)、explained_variance_ratio。"""
    from sklearn.utils.extmath import randomized_svd
    mu = X.mean(0)
    Xc = X - mu
    U, S, Vt = randomized_svd(Xc.astype(np.float64), n_components=k, n_iter=5, random_state=seed)
    total_var = float((Xc.astype(np.float64) ** 2).sum() / (len(X) - 1))
    evr = (S ** 2) / (len(X) - 1) / total_var
    return {"mean": mu.astype(np.float32), "components": Vt.astype(np.float32), "explained_variance_ratio": evr.astype(np.float32),
            "n_fit": len(X), "fit_years": list(FIT_YEARS), "seed": seed}


def transform(X: np.ndarray, pca: dict) -> np.ndarray:
    return (X - pca["mean"]) @ pca["components"].T


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3_base"); ap.add_argument("--text-type", default="body"); ap.add_argument("--cutoff", default="main")
    args = ap.parse_args()
    paths = load_paths()
    agg_dir = Path(paths["agg_dir"]) / args.model / args.text_type / args.cutoff
    out_dir = Path(paths["pca_dir"]) / args.model / args.text_type / args.cutoff; out_dir.mkdir(parents=True, exist_ok=True)
    years = sorted(int(p.stem.split("=")[1]) for p in agg_dir.glob("year=*.parquet"))
    fit_keys, fit_X = [], []
    for y in range(FIT_YEARS[0], FIT_YEARS[1] + 1):
        k, X = load_year(agg_dir, y); fit_keys.append(k); fit_X.append(X)
    fit_keys, fit_X = pl.concat(fit_keys), np.concatenate(fit_X)
    pca = fit_pca(fit_X)
    np.savez(out_dir / "pca_model.npz", **{k: v for k, v in pca.items() if isinstance(v, np.ndarray)})
    Z = transform(fit_X, pca)
    evr = pca["explained_variance_ratio"]
    diag = {"n_fit": int(len(fit_X)), "P": int(fit_X.shape[1]), "cum_evr_64": float(evr[:64].sum()), "cum_evr_256": float(evr.sum()),
            "pc1_corr_news_cnt": float(np.corrcoef(Z[:, 0], fit_keys["news_cnt"].to_numpy())[0, 1]),
            "pc1_corr_n_body": float(np.corrcoef(Z[:, 0], fit_keys["n_body"].to_numpy())[0, 1]),
            "pc1_corr_emb_norm": float(np.corrcoef(Z[:, 0], np.linalg.norm(fit_X, axis=1))[0, 1])}
    for y in years:
        k, X = load_year(agg_dir, y)
        Zy = transform(X, pca).astype(np.float32)
        cols = {"datetime": pa.array(k["datetime"].to_list(), pa.date32()), "instrument": pa.array(k["instrument"].to_list(), pa.string()),
                "news_cnt": pa.array(k["news_cnt"].to_list(), pa.int32())}
        for i in range(K_MAX):
            cols[f"pc_{i}"] = pa.array(Zy[:, i])
        pq.write_table(pa.table(cols), out_dir / f"year={y}.parquet", compression="zstd")
    (out_dir / "_meta.json").write_text(json.dumps({**diag, "fit_years": list(FIT_YEARS), "k_max": K_MAX, "model": args.model, "text_type": args.text_type,
                                                    "cutoff": args.cutoff, "note": "pc64 = 前 64 个主成分；64 维就是 pc_0..pc_63"}, indent=2) + "\n")
    res = ROOT / paths["results"] / "ridge"; res.mkdir(parents=True, exist_ok=True)
    line = (f"| {args.model} | {args.text_type} | {args.cutoff} | {diag['n_fit']:,} | {diag['cum_evr_64']:.1%} | {diag['cum_evr_256']:.1%} | "
            f"{diag['pc1_corr_news_cnt']:+.2f} | {diag['pc1_corr_n_body']:+.2f} | {diag['pc1_corr_emb_norm']:+.2f} |")
    f = res / "pca_summary.md"
    if not f.exists():
        f.write_text("# PCA（只在 2015–2018 拟合）\n\n| 模型 | 文本 | 口径 | 拟合样本 | 64 维累计解释方差 | 256 维 | PC1 与 news_cnt 相关 | PC1 与 n_body | PC1 与嵌入范数 |\n| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |\n")
    f.write_text(f.read_text() + line + "\n")
    print(json.dumps(diag, indent=2)); print(line)


if __name__ == "__main__":
    main()
