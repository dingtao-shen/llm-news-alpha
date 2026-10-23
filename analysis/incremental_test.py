"""模块 5 增量检验：融合（Alpha158 + 新闻 PCA-64）相对纯 Alpha158 的日度 Rank IC 配对差（Newey–West t），
以及纯新闻分数与 Alpha158 分数的日均截面秩相关（文本因子是否只是量价因子的变形）。

输入：pred_dir/qlib__<fs>__<model>__seed<s>.parquet（run_rolling 产出）与 paths.labels 主标签。同一模型、同一种子配对。
输出：results/qlib/incremental.md。运行：python -m analysis.incremental_test
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from analysis.dm_test import nw_tstat
from common import ROOT, load_paths
from models.labels import MAIN_LABEL


def load(pred_dir: Path, fs: str, model: str, seed: int) -> pd.DataFrame | None:
    f = pred_dir / f"qlib__{fs}__{model}__seed{seed}.parquet"
    if not f.exists():
        return None
    return pl.read_parquet(f).to_pandas().set_index(["datetime", "instrument"])["score"]


def daily_rank_ic(score: pd.Series, label: pd.Series) -> pd.Series:
    df = pd.concat([score.rename("s"), label.rename("y")], axis=1, join="inner").dropna()
    return df.groupby(level="datetime")[["s", "y"]].apply(lambda g: g["s"].corr(g["y"], method="spearman") if len(g) >= 20 else np.nan).dropna()


def daily_rank_corr(a: pd.Series, b: pd.Series) -> pd.Series:
    df = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
    return df.groupby(level="datetime")[["a", "b"]].apply(lambda g: g["a"].corr(g["b"], method="spearman") if len(g) >= 20 else np.nan).dropna()


def main() -> None:
    paths = load_paths()
    pred_dir = Path(paths["pred_dir"])
    labels = pl.read_parquet(paths["labels"], columns=["datetime", "instrument", MAIN_LABEL]).to_pandas()
    labels["datetime"] = pd.to_datetime(labels["datetime"]).dt.date
    y = labels.set_index(["datetime", "instrument"])[MAIN_LABEL]
    md = ["# 增量检验：融合 vs Alpha158（日度 Rank IC 配对差，Newey–West 滞后 5）", "",
          "样本 = 成分股全部股票-日（含无新闻的日子，新闻特征为 0）；每行是同一模型、同一种子的配对差，再对种子取均值。", "",
          "| 融合特征集 | 模型 | Alpha158 Rank IC | 融合 Rank IC | 差 | t（种子均值） | 种子 |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for fs in ("fusion_title", "fusion_body"):
        for model, seeds in (("ridge", [0]), ("lgbm", [0, 1, 2]), ("mlp", [0, 1, 2])):
            rows = []
            for s in seeds:
                a, b = load(pred_dir, "alpha158", model, s), load(pred_dir, fs, model, s)
                if a is None or b is None:
                    continue
                ia, ib = daily_rank_ic(a, y), daily_rank_ic(b, y)
                d = (ib - ia).dropna()
                rows.append((ia.mean(), ib.mean(), *nw_tstat(d.to_numpy())))
            if rows:
                r = np.array(rows).mean(0)
                md.append(f"| {fs} | {model} | {r[0]:+.4f} | {r[1]:+.4f} | {r[2]:+.4f} | {r[3]:+.2f} | {len(rows)} |")
    md += ["", "## 纯新闻分数与 Alpha158 分数的日均截面秩相关（同模型、seed 0）", "", "| 新闻特征集 | 模型 | 秩相关均值 | 交易日 |", "| --- | --- | ---: | ---: |"]
    for fs in ("news_title", "news_body"):
        for model in ("ridge", "lgbm", "mlp"):
            a, b = load(pred_dir, "alpha158", model, 0), load(pred_dir, fs, model, 0)
            if a is None or b is None:
                continue
            c = daily_rank_corr(b, a)
            md.append(f"| {fs} | {model} | {c.mean():+.3f} | {len(c)} |")
    res = ROOT / paths["results"] / "qlib"; res.mkdir(parents=True, exist_ok=True)
    (res / "incremental.md").write_text("\n".join(md) + "\n"); print("\n".join(md))


if __name__ == "__main__":
    main()
