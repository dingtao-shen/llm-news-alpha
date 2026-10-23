"""模块 3 任务 6：充分统计量 Ridge（plan.md 第 6 节）。按年累加 X′X、X′1、X′y、y′1，年度滚动：4 年训练 + 1 年验证 + 1 年测试。

- 输入：agg_dir/<model>/<text_type>/<cutoff>/year=YYYY.parquet 与 paths.labels；样本 = in_sp500 且主标签非空的股票-日。
- 每年一份统计量（float64）：n, Xsum(P), XtX(P×P), Xty(P×L), ysum(L)，L 个标签同时累加（主标签、收盘到收盘、建仓推迟 1–4 天）。
- 每个滚动窗口：训练年统计量相加 → 中心化 → 对 S 做一次特征分解 → 整条 λ 路径的解（所有标签一次算出）→
  在验证年按日均 Rank IC 选 λ（每个标签各选）→ 测试年只评估一次。λ 网格相对于 trace(S)/P 取对数等距。
- 输出：pred_dir/<model>__<text_type>__<cutoff>.parquet（datetime, instrument, score=主标签预测, score_<label>…；接口文件 3）；
  results/ridge/<key>.md/.json（每个测试年的 λ、验证 IC、测试 IC/ICIR/Rank IC）。
运行：python -m models.ridge_suffstats --model llama3_base --text-type title --cutoff main
ChronoBERT 按年滚动：每个版本目录只含自己窗口的嵌入，逐个版本跑单个测试年，再由 analysis/table_a.py 拼成一行：
  --model chronobert-20191231 --test-years 2020 … --model chronobert-20221231 --test-years 2023
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import polars as pl
import pyarrow.parquet as pq

from common import ROOT, load_paths
from models.labels import LABELS, MAIN_LABEL

TEST_YEARS = [2020, 2021, 2022, 2023]
N_TRAIN, N_VAL = 4, 1
LAMBDA_REL = np.logspace(-3, 4, 15)      # × trace(S)/P


# ------------------------------------------------------------------ 统计量
def load_year(agg_dir: Path, labels: pl.DataFrame, year: int) -> tuple[np.ndarray, np.ndarray, pl.DataFrame]:
    """返回 X(float64 n×P), Y(n×L), keys(datetime, instrument)；只取 in_sp500 且主标签非空的行。"""
    t = pq.read_table(agg_dir / f"year={year}.parquet")
    keys = pl.from_arrow(t.select(["datetime", "instrument", "in_sp500"])).with_row_index("row")
    emb = np.stack(t["emb"].to_numpy(zero_copy_only=False))
    j = keys.filter(pl.col("in_sp500")).join(labels, on=["datetime", "instrument"], how="inner").filter(pl.col(MAIN_LABEL).is_not_null())
    X = emb[j["row"].to_numpy()].astype(np.float64)
    Y = j.select(list(LABELS)).to_numpy().astype(np.float64)
    Y = np.where(np.isnan(Y), 0.0, Y)          # 次要标签偶有缺失（样本末端），置 0 对均值影响可忽略
    return X, Y, j.select("datetime", "instrument")


def suffstats(X: np.ndarray, Y: np.ndarray) -> dict[str, np.ndarray]:
    return {"n": np.array(len(X)), "Xsum": X.sum(0), "XtX": X.T @ X, "Xty": X.T @ Y, "ysum": Y.sum(0)}


def add_stats(stats: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    return {k: sum(s[k] for s in stats) for k in stats[0]}


def ridge_path(XtX, Xsum, Xty, ysum, n, lambdas):
    """由累加统计量求中心化 Ridge 的整条 λ 路径（plan.md 第 6 节）。Xty: P×L。返回 betas (K×P×L)、intercepts (K×L)、特征值 w。"""
    mu, ybar = Xsum / n, ysum / n
    S = XtX - n * np.outer(mu, mu)
    s = Xty - n * np.outer(mu, ybar)
    w, V = np.linalg.eigh(S)
    w = np.clip(w, 0.0, None)
    z = V.T @ s                                     # P×L
    betas = np.stack([V @ (z / (w + lam)[:, None]) for lam in lambdas])     # K×P×L
    intercepts = ybar[None, :] - np.einsum("kpl,p->kl", betas, mu)
    return betas, intercepts, w


def predict(X: np.ndarray, beta: np.ndarray, intercept: float) -> np.ndarray:
    return X @ beta + intercept


# ------------------------------------------------------------------ 评价
def daily_ic(keys: pl.DataFrame, score: np.ndarray, y: np.ndarray, method: str = "spearman") -> pl.DataFrame:
    df = keys.with_columns(pl.Series("s", score), pl.Series("y", y))
    corr = pl.corr(pl.col("s").rank(), pl.col("y").rank()) if method == "spearman" else pl.corr(pl.col("s"), pl.col("y"))
    return df.group_by("datetime").agg(corr.alias("ic"), pl.len().alias("n")).filter(pl.col("n") >= 5).sort("datetime")


def ic_summary(ic: pl.DataFrame) -> dict:
    v = ic["ic"].drop_nulls()
    return {"mean": float(v.mean()), "icir": float(v.mean() / v.std()) if len(v) > 1 and v.std() else float("nan"), "days": len(v)}


# ------------------------------------------------------------------ 主流程
def run(agg_dir: Path, labels: pl.DataFrame, test_years=TEST_YEARS) -> tuple[pl.DataFrame, dict]:
    years = sorted({int(p.stem.split("=")[1]) for p in agg_dir.glob("year=*.parquet")})
    cache: dict[int, tuple] = {}
    stats: dict[int, dict] = {}

    def get(y):
        if y not in cache:
            X, Y, keys = load_year(agg_dir, labels, y)
            cache[y] = (X, Y, keys); stats[y] = suffstats(X, Y)
        return cache[y]

    labels_list = list(LABELS); mi = labels_list.index(MAIN_LABEL)
    preds, report = [], {"windows": [], "lambda_rel_grid": LAMBDA_REL.tolist(), "n_by_year": {}}
    for ty in test_years:
        train = [y for y in range(ty - N_TRAIN - N_VAL, ty - N_VAL) if y in years]
        val = ty - N_VAL
        if len(train) < N_TRAIN or val not in years or ty not in years:
            print(f"skip test {ty}: train={train} val={val}"); continue
        t0 = time.time()
        for y in train + [val, ty]:
            get(y)
        st = add_stats([stats[y] for y in train])
        P = st["XtX"].shape[0]
        n = int(st["n"])
        mu = st["Xsum"] / n
        trace_rel = (np.trace(st["XtX"]) - n * mu @ mu) / P
        lambdas = LAMBDA_REL * trace_rel
        betas, intercepts, w = ridge_path(st["XtX"], st["Xsum"], st["Xty"], st["ysum"], n, lambdas)
        Xv, Yv, kv = get(val); Xt, Yt, kt = get(ty)
        win = {"test_year": ty, "train_years": train, "val_year": val, "n_train": n, "n_val": len(Xv), "n_test": len(Xt),
               "eig_max": float(w.max()), "eig_median": float(np.median(w)), "trace_over_P": float(trace_rel), "labels": {}}
        scores = {}
        for li, lab in enumerate(labels_list):
            val_ic = [ic_summary(daily_ic(kv, predict(Xv, betas[k, :, li], intercepts[k, li]), Yv[:, li]))["mean"] for k in range(len(lambdas))]
            k_best = int(np.nanargmax(val_ic))
            s_test = predict(Xt, betas[k_best, :, li], intercepts[k_best, li])
            scores[lab] = s_test
            rank = ic_summary(daily_ic(kt, s_test, Yt[:, li])); pear = ic_summary(daily_ic(kt, s_test, Yt[:, li], "pearson"))
            win["labels"][lab] = {"lambda_rel": float(LAMBDA_REL[k_best]), "lambda": float(lambdas[k_best]), "val_rank_ic_curve": [round(x, 5) for x in val_ic],
                                  "val_rank_ic": round(val_ic[k_best], 5), "test_rank_ic": round(rank["mean"], 5), "test_rank_icir": round(rank["icir"], 4),
                                  "test_ic": round(pear["mean"], 5), "test_icir": round(pear["icir"], 4), "test_days": rank["days"]}
        win["secs"] = round(time.time() - t0, 1)
        report["windows"].append(win)
        preds.append(kt.with_columns(pl.Series("score", scores[MAIN_LABEL]), *[pl.Series(f"score_{lab}", scores[lab]) for lab in labels_list if lab != MAIN_LABEL]))
        print(f"test {ty}: n_train={n:,} n_test={len(Xt):,} λ_rel={win['labels'][MAIN_LABEL]['lambda_rel']:.3g} "
              f"main val RankIC={win['labels'][MAIN_LABEL]['val_rank_ic']:+.4f} test RankIC={win['labels'][MAIN_LABEL]['test_rank_ic']:+.4f} "
              f"IC={win['labels'][MAIN_LABEL]['test_ic']:+.4f} ICIR={win['labels'][MAIN_LABEL]['test_icir']:+.3f} ({win['secs']}s)", flush=True)
        for y in [y for y in cache if y < ty - N_TRAIN - N_VAL]:   # 释放不再需要的年份
            cache.pop(y)
    report["n_by_year"] = {y: int(stats[y]["n"]) for y in sorted(stats)}
    pred = pl.concat(preds).sort("datetime", "instrument") if preds else pl.DataFrame()
    if len(pred):
        allk = pl.concat([daily_ic(p.select("datetime", "instrument"), p["score"].to_numpy(), labels.join(p.select("datetime", "instrument"), on=["datetime", "instrument"], how="semi").sort("datetime", "instrument")[MAIN_LABEL].to_numpy()) for p in preds])
        report["overall_main"] = {"rank": ic_summary(allk)}
    return pred, report


def write_report(report: dict, key: str, res: Path) -> None:
    res.mkdir(parents=True, exist_ok=True)
    md = [f"# {key} · 年度滚动 Ridge（4 年训练 + 1 年验证 + 1 年测试）", "",
          f"- λ 网格（相对 trace(S)/P）：{', '.join(f'{x:.3g}' for x in report['lambda_rel_grid'])}；每年样本数：{report['n_by_year']}", "",
          "## 主标签（开盘到开盘）", "", "| 测试年 | 训练年 | n_train | n_test | λ_rel | 验证 Rank IC | 测试 IC | 测试 ICIR | 测试 Rank IC | 测试 Rank ICIR |",
          "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for w in report["windows"]:
        m = w["labels"][MAIN_LABEL]
        md.append(f"| {w['test_year']} | {w['train_years'][0]}–{w['train_years'][-1]} (val {w['val_year']}) | {w['n_train']:,} | {w['n_test']:,} | {m['lambda_rel']:.3g} | "
                  f"{m['val_rank_ic']:+.4f} | {m['test_ic']:+.4f} | {m['test_icir']:+.3f} | {m['test_rank_ic']:+.4f} | {m['test_rank_icir']:+.3f} |")
    if "overall_main" in report:
        o = report["overall_main"]["rank"]
        md += ["", f"- 全测试期（2020–2023）日均 Rank IC **{o['mean']:+.4f}**，Rank ICIR {o['icir']:+.3f}，{o['days']} 个交易日"]
    md += ["", "## 其他标签（测试 Rank IC）", "", "| 测试年 | " + " | ".join(l for l in LABELS if l != MAIN_LABEL) + " |", "| --- |" + " ---: |" * (len(LABELS) - 1)]
    for w in report["windows"]:
        md.append(f"| {w['test_year']} | " + " | ".join(f"{w['labels'][l]['test_rank_ic']:+.4f}" for l in LABELS if l != MAIN_LABEL) + " |")
    (res / f"{key}.md").write_text("\n".join(md) + "\n")
    (res / f"{key}.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print("\n".join(md))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3_base")
    ap.add_argument("--text-type", choices=["title", "body"], required=True)
    ap.add_argument("--cutoff", choices=["main", "1600"], default="main")
    ap.add_argument("--test-years", type=int, nargs="+", default=TEST_YEARS,
                    help="只跑这些测试年（ChronoBERT 每个版本只覆盖自己的 6 年窗口：--model chronobert-20191231 --test-years 2020）")
    args = ap.parse_args()
    paths = load_paths()
    key = f"{args.model}__{args.text_type}__{args.cutoff}"
    agg_dir = Path(paths["agg_dir"]) / args.model / args.text_type / args.cutoff
    labels = pl.read_parquet(paths["labels"])
    pred, report = run(agg_dir, labels, args.test_years)
    out = Path(paths["pred_dir"]); out.mkdir(parents=True, exist_ok=True)
    pred.write_parquet(out / f"{key}.parquet", compression="zstd")
    report.update(model=args.model, text_type=args.text_type, cutoff=args.cutoff, pred=str(out / f"{key}.parquet"), n_pred=len(pred))
    write_report(report, key, ROOT / paths["results"] / "ridge")


if __name__ == "__main__":
    main()
