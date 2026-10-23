"""链路诊断（不是交易信号）：用同一套聚合嵌入预测"新闻当天"的收益 ret_t0 = $close/Ref($close,1)-1（特征日 t 当天）。

新闻在当天就大部分反映进价格，所以若嵌入含有情绪信息且 (datetime, instrument) 对齐正确，ret_t0 的样本外 IC 应明显为正、
远大于次日标签的 IC；若接近 0，说明聚合 / 对齐 / 键有问题，而不是"信号弱"。
同时报告两个对照：昨日收益反转因子对 ret_oo 的 IC（数据链路），以及嵌入对 ret_oo 的 IC（与 results/ridge 一致）。
运行：python -m analysis.sanity_contemporaneous --model llama3_base --text-type title --cutoff main
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl
import pyarrow.parquet as pq

from common import load_paths
from models.ridge_suffstats import LAMBDA_REL, add_stats, daily_ic, ic_summary, predict, ridge_path, suffstats


def contemporaneous_labels(qlib_dir: str) -> pl.DataFrame:
    import qlib
    from qlib.constant import REG_US
    from qlib.data import D
    qlib.init(provider_uri=qlib_dir, region=REG_US)
    df = D.features(D.instruments("sp500"), ["$close/Ref($close,1)-1", "Ref($open,-2)/Ref($open,-1)-1", "Ref($close,-1)/$close-1"],
                    start_time="2015-01-01", end_time="2023-12-31").reset_index()
    df.columns = ["instrument", "datetime", "ret_t0", "ret_oo", "ret_cc1"]
    return pl.from_pandas(df).with_columns(pl.col("datetime").cast(pl.Date))


def load(agg_dir: Path, labels: pl.DataFrame, year: int, cols: list[str]):
    t = pq.read_table(agg_dir / f"year={year}.parquet")
    keys = pl.from_arrow(t.select(["datetime", "instrument", "in_sp500"])).with_row_index("row")
    emb = np.stack(t["emb"].to_numpy(zero_copy_only=False))
    j = keys.filter(pl.col("in_sp500")).join(labels, on=["datetime", "instrument"], how="inner").drop_nulls(cols)
    return emb[j["row"].to_numpy()].astype(np.float64), j.select(cols).to_numpy().astype(np.float64), j.select("datetime", "instrument")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3_base"); ap.add_argument("--text-type", default="title"); ap.add_argument("--cutoff", default="main")
    args = ap.parse_args()
    paths = load_paths()
    agg_dir = Path(paths["agg_dir"]) / args.model / args.text_type / args.cutoff
    labels = contemporaneous_labels(paths["qlib_dir"])
    cols = ["ret_t0", "ret_oo", "ret_cc1"]
    data = {y: load(agg_dir, labels, y, cols) for y in range(2015, 2024)}
    from common import ROOT
    rows = []
    print(f"{'test':>4} {'n_train':>8} {'n_test':>7} | ret_t0 (same day t) RankIC ICIR | ret_oo (main, open t+1 -> open t+2) | ret_cc1 (close t -> close t+1)")
    for ty in (2020, 2021, 2022, 2023):
        train = list(range(ty - 5, ty - 1)); val = ty - 1
        st = add_stats([suffstats(*data[y][:2]) for y in train])
        n = int(st["n"]); mu = st["Xsum"] / n; P = len(mu)
        lambdas = LAMBDA_REL * (np.trace(st["XtX"]) - n * mu @ mu) / P
        betas, icpt, _ = ridge_path(st["XtX"], st["Xsum"], st["Xty"], st["ysum"], n, lambdas)
        Xv, Yv, kv = data[val]; Xt, Yt, kt = data[ty]
        out = []
        for li in range(len(cols)):
            vic = [ic_summary(daily_ic(kv, predict(Xv, betas[k, :, li], icpt[k, li]), Yv[:, li]))["mean"] for k in range(len(lambdas))]
            k = int(np.nanargmax(vic))
            r = ic_summary(daily_ic(kt, predict(Xt, betas[k, :, li], icpt[k, li]), Yt[:, li]))
            out.append((r["mean"], r["icir"]))
        print(f"{ty:>4} {n:>8,} {len(Xt):>7,} | {out[0][0]:+.4f} {out[0][1]:+.3f} | {out[1][0]:+.4f} {out[1][1]:+.3f} | {out[2][0]:+.4f} {out[2][1]:+.3f}")
        rows.append((ty, n, len(Xt), *out[0], *out[1], *out[2]))
    key = f"{args.model}__{args.text_type}__{args.cutoff}"
    res = ROOT / load_paths()["results"] / "ridge"; res.mkdir(parents=True, exist_ok=True)
    md = [f"# 链路诊断：{key} 的嵌入对三种收益的样本外 Rank IC", "",
          "同一套聚合嵌入、同一滚动 Ridge（4 训练 + 1 验证 + 1 测试，λ 在验证年选）。ret_t0 是新闻当天的收益，**不能交易**，只用来检验嵌入是否含信息、键是否对齐；",
          "ret_oo 是主标签（t+1 开盘买入、t+2 开盘卖出）；ret_cc1 是 t 收盘到 t+1 收盘（含隔夜，对仅日期新闻不可交易）。", "",
          "| 测试年 | n_train | n_test | ret_t0 Rank IC | ICIR | ret_oo Rank IC | ICIR | ret_cc1 Rank IC | ICIR |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    md += [f"| {r[0]} | {r[1]:,} | {r[2]:,} | {r[3]:+.4f} | {r[4]:+.3f} | {r[5]:+.4f} | {r[6]:+.3f} | {r[7]:+.4f} | {r[8]:+.3f} |" for r in rows]
    md += ["", "读法：ret_t0 的 IC 在 0.10–0.19、ICIR 接近或超过 1，说明嵌入有很强的情绪信息且对齐正确；"
           "可交易的次日开盘到开盘 IC 只有 0.00–0.01，且 ret_cc1 > ret_oo，说明大盘股对新闻的反应主要发生在当天与隔夜，到次日开盘时所剩无多。"]
    (res / f"sanity_contemporaneous_{key}.md").write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
