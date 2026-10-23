"""模块 6 任务 8：新闻新鲜度。把 Ridge 分数在无新闻的日子里按股票前向填充（最多 5 个交易日），看信号随"距最近一条新闻的天数"衰减多快，
以及"当日有新闻"与"前向填充 5 日"两种特征口径下的全样本 Rank IC（后者覆盖更多股票-日，是模块 4 融合特征的候选处理方式）。
输入：pred_dir 的主口径 pred（ChronoBERT 四版拼接）、paths.labels 主标签、SPY 交易日历。输出：results/ridge/freshness.md。
运行：python -m analysis.freshness
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from analysis.dm_test import nw_tstat
from analysis.longshort import NAMES, TEXT, load_preds
from common import ROOT, load_paths
from models.labels import MAIN_LABEL

FOCUS = ["chronobert__body", "llama3_base__body", "llama3_base__title", "tfidf__body"]
MAX_AGE = 5


def rank_ic_by_group(df: pd.DataFrame, group: str) -> list[tuple]:
    out = []
    for g, part in df.groupby(group, observed=True):
        ic = part.groupby("datetime")[["score", MAIN_LABEL]].apply(lambda x: x["score"].corr(x[MAIN_LABEL], method="spearman") if len(x) >= 5 else np.nan).dropna()
        mu, t = nw_tstat(ic.to_numpy()) if len(ic) > 10 else (np.nan, np.nan)
        out.append((g, len(part), len(ic), mu, t))
    return out


def main() -> None:
    paths = load_paths()
    labels = pl.read_parquet(paths["labels"], columns=["datetime", "instrument", MAIN_LABEL]).to_pandas()
    labels["datetime"] = pd.to_datetime(labels["datetime"])
    lab = labels[(labels["datetime"] >= "2020-01-01") & (labels["datetime"] <= "2023-12-31")]
    cal = pd.DatetimeIndex(sorted(lab["datetime"].unique()))
    preds = load_preds(Path(paths["pred_dir"]))
    md = ["# 新闻新鲜度：分数前向填充后按\"距最近新闻的交易日数\"分组的 Rank IC（2020–2023，NW t）", "",
          "age=0 为当日有新闻（主口径样本）；age=k 表示用 k 个交易日前的最近一条新闻的分数。\"填充 5 日\"一行把 age 0–5 合并评估，对应模块 4 融合特征的前向填充口径。", ""]
    for key in [k for k in FOCUS if k in preds]:
        S = preds[key].reindex(index=cal)                               # 日 × 股票，NaN = 无新闻
        age = S.notna().astype(int)
        filled = S.ffill(limit=MAX_AGE)
        # 距最近新闻的交易日数：有新闻为 0，否则累计
        cnt = (~S.notna()).astype(int)
        age_arr = np.zeros(S.shape, dtype=int)
        a = np.zeros(S.shape[1], dtype=int)
        for i in range(S.shape[0]):
            a = np.where(S.iloc[i].notna().to_numpy(), 0, a + 1); age_arr[i] = a
        long = pd.DataFrame({"score": filled.stack(), "age": pd.DataFrame(age_arr, index=S.index, columns=S.columns).stack()}).reset_index()
        long.columns = ["datetime", "instrument", "score", "age"]
        long = long.merge(lab, on=["datetime", "instrument"], how="inner").dropna(subset=["score", MAIN_LABEL])
        long = long[long["age"] <= MAX_AGE]
        long["age_group"] = long["age"].map(lambda k: str(k) if k <= 2 else "3–5")
        rows = rank_ic_by_group(long, "age_group")
        pooled = rank_ic_by_group(long.assign(all="0–5 合并（填充 5 日）"), "all")[0]
        md += [f"## {NAMES[key.split('__')[0]]} / {TEXT[key.split('__')[1]]}", "", "| 距最近新闻的交易日数 | 股票-日 | 交易日 | Rank IC | t |", "| --- | ---: | ---: | ---: | ---: |"]
        md += [f"| {g} | {n:,} | {d} | {mu:+.4f} | {t:+.2f} |" for g, n, d, mu, t in sorted(rows, key=lambda r: r[0])]
        md.append(f"| **{pooled[0]}** | {pooled[1]:,} | {pooled[2]} | {pooled[3]:+.4f} | {pooled[4]:+.2f} |"); md.append("")
    (ROOT / paths["results"] / "ridge" / "freshness.md").write_text("\n".join(md) + "\n"); print("\n".join(md))


if __name__ == "__main__":
    main()
