"""模块 6 任务 1–2：五分位多空（等权、美元中性、开盘到开盘、日频换仓）、换手成本、EWCT 换手控制。

- 每个特征日 t，对当天有预测（有新闻）的股票按 score 排序：最高 20% 等权做多（权重和 +1）、最低 20% 等权做空（权重和 −1）；
  当天不足 MIN_NAMES 只股票则目标权重为 0。目标权重 w*_t 在 t+1 开盘建仓、t+2 开盘换仓，收益用标签 ret_oo。
- EWCT：w_t = ω·w*_t + (1−ω)·w_{t−1}（ω=1 即每日完全换仓）。持仓里没新闻的股票权重按 (1−ω) 衰减，它们的收益同样计入（用全成分股的 ret_oo）。
- 成本：cost_t = c × Σ_i |w_{i,t} − w_{i,t−1}|，c 为每 100% 交易额的费率（基准 10 bps，敏感性 0/5/10/20 bps）。
- 指标：年化收益、年化波动、夏普（×√252）、日均换手 Σ|Δw|、扣费后夏普；按年夏普。
市值加权要等模块 1 任务 6 的历史市值，这里只做等权。
运行：python -m analysis.longshort → results/longshort/
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from common import ROOT, load_paths
from models.labels import MAIN_LABEL

MIN_NAMES = 10
OMEGAS = [1.0, 0.9, 0.7, 0.5, 0.3, 0.2, 0.1]
COSTS_BPS = [0, 5, 10, 20]
ANN = 252


def quintile_weights(scores: pd.DataFrame, min_names: int = MIN_NAMES, n_groups: int = 5, size: pd.DataFrame | None = None) -> pd.DataFrame:
    """scores: 行 = 日期，列 = 股票，NaN = 当天无预测。返回美元中性的目标权重矩阵（同形状，0 填充）：
    做多最高 1/n_groups、做空最低 1/n_groups；size 为 None 时等权，否则按 size（市值）加权，size 缺失的股票不进组合。"""
    W = pd.DataFrame(0.0, index=scores.index, columns=scores.columns)
    for d, row in scores.iterrows():
        s = row.dropna()
        if size is not None and d in size.index:
            sz = size.loc[d].reindex(s.index)
            s = s[sz.notna() & (sz > 0)]
        n = len(s)
        if n < min_names:
            continue
        k = max(int(np.floor(n / n_groups)), 1)
        order = s.sort_values(kind="mergesort")
        long, short = order.index[-k:], order.index[:k]
        if size is None:
            W.loc[d, long] = 1.0 / k; W.loc[d, short] = -1.0 / k
        else:
            wl, ws = size.loc[d, long], size.loc[d, short]
            W.loc[d, long] = (wl / wl.sum()).values; W.loc[d, short] = -(ws / ws.sum()).values
    return W


def ewct(W_target: pd.DataFrame, omega: float) -> pd.DataFrame:
    """w_t = ω w*_t + (1−ω) w_{t−1}。"""
    if omega >= 1.0:
        return W_target
    out = np.zeros(W_target.shape)
    prev = np.zeros(W_target.shape[1])
    tgt = W_target.to_numpy()
    for i in range(len(tgt)):
        prev = omega * tgt[i] + (1 - omega) * prev
        out[i] = prev
    return pd.DataFrame(out, index=W_target.index, columns=W_target.columns)


def portfolio_series(W: pd.DataFrame, R: pd.DataFrame) -> pd.DataFrame:
    """逐日：gross 收益、换手 Σ|Δw|、总敞口 Σ|w|。R 与 W 同形状，NaN 收益按 0（极少数退市日）。"""
    Rz = R.reindex_like(W).fillna(0.0)
    gross = (W * Rz).sum(axis=1)
    dW = W.diff(); dW.iloc[0] = W.iloc[0]
    turnover = dW.abs().sum(axis=1)
    exposure = W.abs().sum(axis=1)
    return pd.DataFrame({"gross": gross, "turnover": turnover, "exposure": exposure})


def summarize(ps: pd.DataFrame, cost_bps: float) -> dict:
    net = ps["gross"] - cost_bps / 1e4 * ps["turnover"]
    active = ps["exposure"] > 1e-9
    def sharpe(x):
        return float(x.mean() / x.std() * np.sqrt(ANN)) if x.std() > 0 else float("nan")
    return {"ann_return_gross": float(ps["gross"].mean() * ANN), "ann_vol": float(ps["gross"].std() * np.sqrt(ANN)),
            "sharpe_gross": sharpe(ps["gross"]), "ann_return_net": float(net.mean() * ANN), "sharpe_net": sharpe(net),
            "turnover_daily": float(ps["turnover"].mean()), "exposure_daily": float(ps["exposure"].mean()),
            "active_days": int(active.sum()), "days": int(len(ps))}


def load_returns(labels_path: str, start: str, end: str, label: str = MAIN_LABEL) -> pd.DataFrame:
    lab = pl.read_parquet(labels_path, columns=["datetime", "instrument", label]).filter(pl.col("datetime").is_between(pl.lit(start).str.to_date(), pl.lit(end).str.to_date()))
    return lab.to_pandas().pivot(index="datetime", columns="instrument", values=label)


def load_size(mcap_path: str, start: str, end: str) -> pd.DataFrame:
    """市值矩阵（SEC 股数 × 收盘价；缺失为 NaN，加权时跳过）。"""
    m = pl.read_parquet(mcap_path, columns=["datetime", "instrument", "mcap"]).filter(pl.col("datetime").is_between(pl.lit(start).str.to_date(), pl.lit(end).str.to_date()))
    return m.to_pandas().pivot(index="datetime", columns="instrument", values="mcap")


def load_preds(pred_dir: Path) -> dict[str, pd.DataFrame]:
    """key = model__text；ChronoBERT 四个版本拼成一个。返回 score 透视表。"""
    groups: dict[str, list[pl.DataFrame]] = {}
    for f in sorted(pred_dir.glob("*__main.parquet")):
        model, text, _ = f.stem.split("__")
        key = f"{'chronobert' if model.startswith('chronobert-') else model}__{text}"
        groups.setdefault(key, []).append(pl.read_parquet(f, columns=["datetime", "instrument", "score"]))
    out = {}
    for key, parts in groups.items():
        df = pl.concat(parts).unique(subset=["datetime", "instrument"], keep="last").to_pandas()
        out[key] = df.pivot(index="datetime", columns="instrument", values="score")
    return out


def run_all(preds: dict[str, pd.DataFrame], R: pd.DataFrame, n_groups: int = 5, size: pd.DataFrame | None = None) -> tuple[dict, pd.DataFrame]:
    results, daily = {}, {}
    for key, S in preds.items():
        S = S.reindex(index=R.index)                       # 没预测的日子 → 空仓
        Wt = quintile_weights(S.reindex(columns=R.columns), n_groups=n_groups, size=size.reindex(index=R.index, columns=R.columns) if size is not None else None)
        results[key] = {"omegas": {}, "by_year_gross_sharpe": {}}
        for om in OMEGAS:
            ps = portfolio_series(ewct(Wt, om), R)
            results[key]["omegas"][str(om)] = {f"cost_{c}bps": summarize(ps, c) for c in COSTS_BPS}
            if om == 1.0:
                daily[key] = ps["gross"]
                for y, g in ps.groupby(ps.index.year):
                    results[key]["by_year_gross_sharpe"][int(y)] = summarize(g, 0)["sharpe_gross"]
    return results, pd.DataFrame(daily)


NAMES = {"llama3_base": "LLaMA3-8B", "chronobert": "ChronoBERT（按年滚动）", "finbert": "FinBERT", "minilm": "MiniLM",
         "tfidf": "TF-IDF + Ridge", "lm_dict": "LM 词典"}
TEXT = {"title": "标题", "body": "原文", "summary": "摘要"}
ORDER = ["llama3_base", "chronobert", "finbert", "minilm", "tfidf", "lm_dict"]


def write_report(results: dict, daily: pd.DataFrame, res: Path, variant: str = "", title: str = "五分位多空（等权）") -> None:
    res.mkdir(parents=True, exist_ok=True)
    keys = [f"{m}__{t}" for m in ORDER for t in ("title", "body", "summary") if f"{m}__{t}" in results]
    label = lambda k: f"{NAMES[k.split('__')[0]]} / {TEXT[k.split('__')[1]]}"
    md = [f"# {title}：夏普、换手与成本", "",
          f"测试期 2020–2023，每日按 score 做多前 20%、做空后 20%（有新闻的股票中），t+1 开盘建仓、t+2 开盘换仓；不足 {MIN_NAMES} 只的日子空仓。"
          "成本 = 费率 × Σ|Δw|（每 100% 交易额）。市值加权待历史市值（模块 1 任务 6）。", "",
          "## 每日完全换仓（ω = 1）", "",
          "| 模型 / 文本 | 年化收益 | 年化波动 | 夏普（毛） | 日均换手 Σ\\|Δw\\| | 净夏普 @5 bps | 净夏普 @10 bps | 净夏普 @20 bps | 有仓位天数 |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for k in keys:
        r = results[k]["omegas"]["1.0"]; g = r["cost_0bps"]
        md.append(f"| {label(k)} | {g['ann_return_gross']:+.1%} | {g['ann_vol']:.1%} | {g['sharpe_gross']:+.2f} | {g['turnover_daily']:.2f} | "
                  f"{r['cost_5bps']['sharpe_net']:+.2f} | {r['cost_10bps']['sharpe_net']:+.2f} | {r['cost_20bps']['sharpe_net']:+.2f} | {g['active_days']}/{g['days']} |")
    md += ["", "## EWCT 换手控制：ω 从 1（完全换仓）到 0.1；每格为 毛夏普 / 净夏普@10 bps（日均换手）", "",
           "| 模型 / 文本 | " + " | ".join(f"ω={o}" for o in OMEGAS) + " |", "| --- |" + " ---: |" * len(OMEGAS)]
    for k in keys:
        cells = []
        for o in OMEGAS:
            r = results[k]["omegas"][str(o)]
            cells.append(f"{r['cost_0bps']['sharpe_gross']:+.2f} / {r['cost_10bps']['sharpe_net']:+.2f} ({r['cost_0bps']['turnover_daily']:.2f})")
        md.append(f"| {label(k)} | " + " | ".join(cells) + " |")
    md += ["", "## 按年毛夏普（ω = 1）", "", "| 模型 / 文本 | 2020 | 2021 | 2022 | 2023 |", "| --- | ---: | ---: | ---: | ---: |"]
    for k in keys:
        by = results[k]["by_year_gross_sharpe"]
        md.append(f"| {label(k)} | " + " | ".join(f"{by.get(y, float('nan')):+.2f}" for y in (2020, 2021, 2022, 2023)) + " |")
    md += ["", f"![cum](longshort_cum_gross{variant}.png)"]
    (res / f"sharpe_table{variant}.md").write_text("\n".join(md) + "\n")
    (res / f"sharpe_table{variant}.json").write_text(json.dumps(results, indent=2) + "\n")
    daily.to_csv(res / f"daily_longshort_gross_omega1{variant}.csv", float_format="%.6f")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4.8))
    en = {"llama3_base": "LLaMA3-8B", "chronobert": "ChronoBERT (rolling)", "finbert": "FinBERT", "minilm": "MiniLM", "tfidf": "TF-IDF+Ridge", "lm_dict": "LM dictionary"}
    for k in keys:   # 图例用英文：服务器字体没有中文字形
        m, t = k.split("__")
        ax.plot(daily.index, daily[k].cumsum(), label=f"{en[m]} / {t}", lw=1.2)
    ax.axhline(0, color="k", lw=0.5); ax.set_ylabel("cumulative gross long-short return (ω=1, equal-weight)"); ax.grid(alpha=0.3); ax.legend(fontsize=7, ncol=2)
    fig.tight_layout(); fig.savefig(res / f"longshort_cum_gross{variant}.png", dpi=130); plt.close(fig)
    print("\n".join(md))


def delay_table(preds: dict[str, pd.DataFrame], paths: dict, start: str, end: str, res: Path) -> None:
    """新闻动量衰减（原文表 18）：建仓推迟 k 天（k=0..4）的等权五分位多空毛夏普与年化收益。"""
    keys = [f"{m}__{t}" for m in ORDER for t in ("title", "body", "summary") if f"{m}__{t}" in preds]
    label = lambda k: f"{NAMES[k.split('__')[0]]} / {TEXT[k.split('__')[1]]}"
    labels = [MAIN_LABEL] + [f"ret_oo_d{k}" for k in range(1, 5)]
    rows = {}
    for lab in labels:
        R = load_returns(paths["labels"], start, end, lab)
        for key in keys:
            S = preds[key].reindex(index=R.index)
            ps = portfolio_series(quintile_weights(S.reindex(columns=R.columns)), R)
            st = summarize(ps, 0)
            rows.setdefault(key, {})[lab] = (st["sharpe_gross"], st["ann_return_gross"])
    md = ["# 建仓推迟 k 天的等权五分位多空（毛夏普 / 年化收益）", "", "k=0 为主口径（t+1 开盘建仓、t+2 开盘换仓）；k 天后再建仓，持有一天。", "",
          "| 模型 / 文本 | " + " | ".join(f"k={k}" for k in range(5)) + " |", "| --- |" + " ---: |" * 5]
    for key in keys:
        md.append(f"| {label(key)} | " + " | ".join(f"{rows[key][l][0]:+.2f} / {rows[key][l][1]:+.1%}" for l in labels) + " |")
    (res / "delay_table.md").write_text("\n".join(md) + "\n"); print("\n".join(md))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2020-01-01"); ap.add_argument("--end", default="2023-12-31")
    ap.add_argument("--variants", nargs="+", default=["ew", "vw", "decile", "delay"], help="ew 等权五分位 | vw 市值加权五分位 | decile 等权十分组 | delay 建仓推迟表")
    args = ap.parse_args()
    paths = load_paths()
    res = ROOT / paths["results"] / "longshort"
    R = load_returns(paths["labels"], args.start, args.end)
    preds = load_preds(Path(paths["pred_dir"]))
    print(f"returns {R.shape}; preds: {', '.join(f'{k} {v.shape}' for k, v in preds.items())}", flush=True)
    if "ew" in args.variants:
        results, daily = run_all(preds, R); write_report(results, daily, res)
    if "vw" in args.variants:
        size = load_size(paths["market_cap"], args.start, args.end)
        results, daily = run_all(preds, R, size=size); write_report(results, daily, res, "_vw", "五分位多空（市值加权，缺市值的股票不入组合）")
    if "decile" in args.variants:
        results, daily = run_all(preds, R, n_groups=10); write_report(results, daily, res, "_decile", "十分组多空（等权）")
    if "delay" in args.variants:
        delay_table(preds, paths, args.start, args.end, res)


if __name__ == "__main__":
    main()
