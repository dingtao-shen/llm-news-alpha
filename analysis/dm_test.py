"""模型间比较的显著性：以日度 Rank IC 为"预测精度"，对每对模型做 Diebold–Mariano 型检验（配对差 d_t = IC_i,t − IC_j,t，
Newey–West HAC 标准误，滞后 LAG），同时给出每个模型 IC 对 0 的 HAC t 值。

输入：pred_dir 里的 *__main.parquet（ChronoBERT 四版拼接）与 paths.labels 的主标签；只用两模型都有 IC 的交易日。
输出：results/ridge/dm_test.md / .json。运行：python -m analysis.dm_test
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from analysis.longshort import NAMES, ORDER, TEXT, load_preds
from common import ROOT, load_paths
from models.labels import MAIN_LABEL

LAG = 5


def nw_tstat(d: np.ndarray, lag: int = LAG) -> tuple[float, float]:
    """均值的 Newey–West t 统计量（Bartlett 核）。返回 (mean, t)。"""
    d = np.asarray(d, dtype=float); d = d[~np.isnan(d)]
    n = len(d); mu = d.mean(); e = d - mu
    s = e @ e / n
    for k in range(1, lag + 1):
        w = 1 - k / (lag + 1)
        s += 2 * w * (e[k:] @ e[:-k]) / n
    return float(mu), float(mu / np.sqrt(s / n)) if s > 0 else float("nan")


def daily_rank_ic(pred: pd.DataFrame, labels: pd.DataFrame) -> pd.Series:
    df = pred.stack().rename("score").reset_index().merge(labels, on=["datetime", "instrument"], how="inner")
    ic = df.groupby("datetime")[["score", MAIN_LABEL]].apply(lambda g: g["score"].corr(g[MAIN_LABEL], method="spearman") if len(g) >= 5 else np.nan)
    return ic.dropna()


def main() -> None:
    paths = load_paths()
    labels = pl.read_parquet(paths["labels"], columns=["datetime", "instrument", MAIN_LABEL]).to_pandas()
    preds = load_preds(Path(paths["pred_dir"]))
    keys = [f"{m}__{t}" for m in ORDER for t in ("title", "body", "summary") if f"{m}__{t}" in preds]
    ics = pd.DataFrame({k: daily_rank_ic(preds[k], labels) for k in keys})
    label = lambda k: f"{NAMES[k.split('__')[0]]} / {TEXT[k.split('__')[1]]}"
    single = {k: nw_tstat(ics[k].to_numpy()) for k in keys}
    mat = pd.DataFrame(index=keys, columns=keys, dtype=float)
    for i in keys:
        for j in keys:
            if i != j:
                d = (ics[i] - ics[j]).dropna()
                mat.loc[i, j] = nw_tstat(d.to_numpy())[1]
    md = ["# 模型间 Diebold–Mariano 型检验（日度 Rank IC，Newey–West 滞后 5）", "",
          f"测试期 2020–2023，共 {len(ics)} 个交易日。先看每个模型的 IC 是否显著异于 0，再看两两之差。", "",
          "| 模型 / 文本 | 日均 Rank IC | HAC t | 交易日 |", "| --- | ---: | ---: | ---: |"]
    md += [f"| {label(k)} | {single[k][0]:+.4f} | {single[k][1]:+.2f} | {ics[k].notna().sum()} |" for k in keys]
    md += ["", "## 两两之差的 t 值（行 − 列；|t| > 1.96 为 5% 显著）", "", "| 行 \\ 列 | " + " | ".join(label(k) for k in keys) + " |", "| --- |" + " ---: |" * len(keys)]
    for i in keys:
        md.append(f"| {label(i)} | " + " | ".join("–" if i == j else f"{mat.loc[i, j]:+.2f}" for j in keys) + " |")
    sig = [(label(i), label(j), float(mat.loc[i, j])) for i in keys for j in keys if i != j and abs(mat.loc[i, j]) > 1.96 and mat.loc[i, j] > 0]
    md += ["", f"显著优于另一模型的配对（5% 水平）：{len(sig)} 对 / {len(keys) * (len(keys) - 1) // 2}", ""]
    md += [f"- {a} > {b}：t = {t:+.2f}" for a, b, t in sorted(sig, key=lambda x: -x[2])]
    res = ROOT / paths["results"] / "ridge"
    (res / "dm_test.md").write_text("\n".join(md) + "\n")
    (res / "dm_test.json").write_text(json.dumps({"single": {k: {"mean": v[0], "t": v[1]} for k, v in single.items()},
                                                   "pairwise_t": mat.round(3).to_dict()}, indent=2) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
