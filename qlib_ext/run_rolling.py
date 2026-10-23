"""模块 4 任务 4 + 模块 5 任务 2：年度滚动（4 年训练 + 1 年验证 + 1 年测试，测试 2020–2023）× 特征集 × 模型 × 种子 → 表 B。

特征集（NewsAlpha158Handler，数据 paths.qlib_news_dir）：
  alpha158 | news_title（PCA-64 标题 + news_cnt + has_news）| news_body | fusion_title（alpha158 + news_title）| fusion_body
模型：ridge（qlib_ext.models.RidgeModel，alpha 在验证年选）、lgbm（LGBModel，验证年早停）、mlp（DNNModelPytorch 2×256，验证年早停，CPU/GPU 可选）。
每个窗口的标准化（RobustZScoreNorm）只在该窗口训练期拟合；标签 CSRankNorm 只用于学习；IC 用测试段的原始标签算。
输出：pred_dir/qlib__<fs>__<model>__seed<s>.parquet（4 个测试年拼接），results/qlib/table_b.{md,json}。
运行：bash infra/run_bg.sh table-b python -m qlib_ext.run_rolling [--models ridge lgbm mlp] [--seeds 0 1 2] [--gpu -1]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from common import ROOT, load_paths, ncpu

TEST_YEARS = [2020, 2021, 2022, 2023]
FEATURE_SETS = {"alpha158": (("alpha158",), "body"), "news_title": (("news",), "title"), "news_body": (("news",), "body"),
                "fusion_title": (("alpha158", "news"), "title"), "fusion_body": (("alpha158", "news"), "body")}
LGB_PARAMS = dict(loss="mse", learning_rate=0.03, num_leaves=63, max_depth=-1, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                  lambda_l1=10.0, lambda_l2=100.0, min_data_in_leaf=200, early_stopping_rounds=50, num_boost_round=1000, verbosity=-1)


def ic_stats(pred: pd.Series, label: pd.Series) -> dict:
    df = pd.DataFrame({"p": pred, "y": label}).dropna()
    g = df.groupby(level="datetime")
    ic = g.apply(lambda x: x["p"].corr(x["y"]) if len(x) >= 5 else np.nan).dropna()
    ric = g.apply(lambda x: x["p"].corr(x["y"], method="spearman") if len(x) >= 5 else np.nan).dropna()
    return {"ic": float(ic.mean()), "icir": float(ic.mean() / ic.std()), "rank_ic": float(ric.mean()), "rank_icir": float(ric.mean() / ric.std()),
            "days": int(len(ric)), "n": int(len(df))}


def make_dataset(qlib_news_dir: str, fs: str, ty: int):
    from qlib.data.dataset import DatasetH
    from qlib_ext.handler import NewsAlpha158Handler
    feature_set, news_text = FEATURE_SETS[fs]
    tr0, tr1, va, te = ty - 5, ty - 2, ty - 1, ty
    h = NewsAlpha158Handler(instruments="sp500", start_time=f"{tr0}-01-01", end_time=f"{te + 1}-01-31", fit_start_time=f"{tr0}-01-01",
                            fit_end_time=f"{tr1}-12-31", feature_set=feature_set, news_text=news_text)
    return DatasetH(handler=h, segments={"train": (f"{tr0}-01-01", f"{tr1}-12-31"), "valid": (f"{va}-01-01", f"{va}-12-31"), "test": (f"{te}-01-01", f"{te}-12-31")})


def make_model(name: str, seed: int, gpu: int, input_dim: int = 0):
    if name == "ridge":
        from qlib_ext.models import RidgeModel
        return RidgeModel()
    if name == "lgbm":
        from qlib.contrib.model.gbdt import LGBModel
        return LGBModel(num_threads=ncpu(), seed=seed, **LGB_PARAMS)
    if name == "mlp":
        from qlib.contrib.model.pytorch_nn import DNNModelPytorch
        return DNNModelPytorch(lr=0.001, max_steps=3000, batch_size=4096, early_stop_rounds=50, eval_steps=20, optimizer="adam", loss="mse",
                               GPU=gpu, seed=seed, weight_decay=1e-4, pt_model_kwargs={"input_dim": input_dim, "layers": (256, 256)})
    raise ValueError(name)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feature-sets", nargs="+", default=list(FEATURE_SETS))
    ap.add_argument("--models", nargs="+", default=["ridge", "lgbm", "mlp"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--test-years", nargs="+", type=int, default=TEST_YEARS)
    ap.add_argument("--gpu", type=int, default=-1, help="MLP 用的 GPU 编号，-1 为 CPU（vLLM 占 GPU 时）")
    args = ap.parse_args()
    paths = load_paths()
    import qlib, torch
    from qlib.constant import REG_US
    from qlib.data.dataset.handler import DataHandlerLP
    qlib.init(provider_uri=paths["qlib_news_dir"], region=REG_US)
    torch.set_num_threads(min(8, ncpu()))
    out_pred = Path(paths["pred_dir"]); out_pred.mkdir(parents=True, exist_ok=True)
    res_dir = ROOT / paths["results"] / "qlib"; res_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    t_all = time.time()
    for fs in args.feature_sets:
        for ty in args.test_years:
            t0 = time.time()
            ds = make_dataset(paths["qlib_news_dir"], fs, ty)
            te = ds.prepare("test", col_set=["feature", "label"], data_key=DataHandlerLP.DK_I)
            y_te = te["label"].iloc[:, 0]
            print(f"[{fs} {ty}] data ready: train/valid/test features {te['feature'].shape[1]}, test rows {len(te):,} ({time.time() - t0:.0f}s)", flush=True)
            for mname in args.models:
                for seed in (args.seeds if mname != "ridge" else [0]):
                    t1 = time.time()
                    m = make_model(mname, seed, args.gpu, input_dim=te["feature"].shape[1])
                    m.fit(ds)
                    pred = m.predict(ds, "test")
                    st = ic_stats(pred, y_te)
                    key = f"qlib__{fs}__{mname}__seed{seed}"
                    r = results.setdefault(key, {"feature_set": fs, "model": mname, "seed": seed, "windows": {}, "preds": []})
                    r["windows"][ty] = {**st, "secs": round(time.time() - t1, 1), **({"alpha": m.alpha_} if mname == "ridge" else {})}
                    r["preds"].append(pred.rename("score").reset_index())
                    print(f"  {mname} seed{seed}: IC {st['ic']:+.4f} RankIC {st['rank_ic']:+.4f} ICIR {st['icir']:+.3f} ({time.time() - t1:.0f}s)", flush=True)
            del ds
    rows = []
    for key, r in results.items():
        pred = pd.concat(r.pop("preds")).sort_values(["datetime", "instrument"])
        pl.from_pandas(pred).with_columns(pl.col("datetime").cast(pl.Date)).write_parquet(out_pred / f"{key}.parquet")
        w = r["windows"]; days = sum(v["days"] for v in w.values())
        r["overall"] = {k: float(sum(v[k] * v["days"] for v in w.values()) / days) for k in ("ic", "rank_ic")}
        rows.append({"feature_set": r["feature_set"], "model": r["model"], "seed": r["seed"], **r["overall"], **{f"ric_{y}": w[y]["rank_ic"] for y in w}})
    df = pd.DataFrame(rows)
    agg = df.groupby(["feature_set", "model"]).agg(ic_mean=("ic", "mean"), ic_std=("ic", "std"), ric_mean=("rank_ic", "mean"), ric_std=("rank_ic", "std"),
                                                     n_seeds=("seed", "count")).reset_index()
    md = ["# 表 B：特征集 × 模型（年度滚动 4+1+1，测试 2020–2023；全期为各年按交易日加权；均值 ± 标准差为种子间）", "",
          f"数据 `{paths['qlib_news_dir']}`；新闻特征 = LLaMA3 PCA-64 + news_cnt + has_news；无新闻的股票-日新闻特征为 0。", "",
          "| 特征集 | 模型 | 全期 IC | 全期 Rank IC | 种子数 |", "| --- | --- | ---: | ---: | ---: |"]
    for _, a in agg.iterrows():
        sd = lambda v: f" ± {v:.4f}" if not np.isnan(v) else ""
        md.append(f"| {a.feature_set} | {a.model} | {a.ic_mean:+.4f}{sd(a.ic_std)} | {a.ric_mean:+.4f}{sd(a.ric_std)} | {a.n_seeds} |")
    md += ["", "## 按测试年 Rank IC（种子均值）", "", "| 特征集 | 模型 | " + " | ".join(str(y) for y in args.test_years) + " |", "| --- | --- |" + " ---: |" * len(args.test_years)]
    for (fs, mn), g in df.groupby(["feature_set", "model"]):
        md.append(f"| {fs} | {mn} | " + " | ".join(f"{g[f'ric_{y}'].mean():+.4f}" if f"ric_{y}" in g else "–" for y in args.test_years) + " |")
    (res_dir / "table_b.md").write_text("\n".join(md) + "\n")
    (res_dir / "table_b.json").write_text(json.dumps({k: {kk: vv for kk, vv in v.items()} for k, v in results.items()}, indent=2, default=str) + "\n")
    print("\n".join(md)); print(f"total {(time.time() - t_all) / 60:.0f} min")


if __name__ == "__main__":
    main()
