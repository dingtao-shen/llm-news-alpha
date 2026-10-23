"""信号去向拆分：同一组预测分数（主口径 Ridge）对不同收益窗口、不同子样本的日度 Rank IC。

收益窗口（相对特征日 t）：
  same_day   = $close/Ref($close,1)-1            新闻当天（不可交易，诊断用）
  overnight  = Ref($open,-1)/$close-1            t 收盘 → t+1 开盘（仅日期新闻不可交易；有时刻新闻中 16:00 前发布的可交易）
  next_intra = Ref($close,-1)/Ref($open,-1)-1    t+1 开盘 → t+1 收盘
  main(ret_oo) = Ref($open,-2)/Ref($open,-1)-1   t+1 开盘 → t+2 开盘（可交易主标签）
子样本（主标签）：
  按来源：该股票-日新闻中 Benzinga（只有标题）的占比 = 0 / (0,1) / 1；
  按新闻条数：1 / 2–3 / ≥4；
  按当天收益幅度 |same_day| 的日内三分位（反应大的新闻日是否还有残余）；
  按市值日内三分位（原文的核心机制：信号在小盘股更强；S&P 500 内部按 SEC 市值分组，缺市值的股票不入分组）。
运行：python -m analysis.signal_decomposition → results/ridge/signal_decomposition.md
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import polars as pl

from analysis.dm_test import nw_tstat
from analysis.longshort import NAMES, ORDER, TEXT, load_preds
from common import ROOT, load_paths

WINDOWS = {"same_day": "$close/Ref($close,1)-1", "overnight": "Ref($open,-1)/$close-1",
           "next_intra": "Ref($close,-1)/Ref($open,-1)-1", "main_oo": "Ref($open,-2)/Ref($open,-1)-1"}
FOCUS = ["chronobert__body", "llama3_base__body", "llama3_base__title", "finbert__title"]


def returns_table(qlib_dir: str) -> pd.DataFrame:
    import qlib
    from qlib.constant import REG_US
    from qlib.data import D
    qlib.init(provider_uri=qlib_dir, region=REG_US)
    df = D.features(D.instruments("sp500"), list(WINDOWS.values()), start_time="2020-01-01", end_time="2023-12-31").reset_index()
    df.columns = ["instrument", "datetime", *WINDOWS.keys()]
    df["datetime"] = pd.to_datetime(df["datetime"]).dt.date
    return df


def source_share(paths: dict) -> pd.DataFrame:
    """每个 (feature_day, ticker) 的 Benzinga 占比与新闻条数（news_clean ⋈ fnspid url_host）。"""
    con = duckdb.connect(); con.execute("SET threads=8"); con.execute("SET enable_progress_bar=false")
    q = f"""
      WITH h AS (SELECT DISTINCT news_id, url_host FROM read_parquet('{paths["news"]["parquet_dir"]}/nasdaq/*.parquet'))
      SELECT c.feature_day AS datetime, c.ticker AS instrument, count(*) AS news_cnt,
             avg((h.url_host = 'benzinga.com')::INT) AS benzinga_share
      FROM read_parquet('{paths["news"]["clean"]}') c LEFT JOIN h USING (news_id)
      WHERE c.in_sp500 GROUP BY 1, 2"""
    df = con.execute(q).df()
    df["datetime"] = pd.to_datetime(df["datetime"]).dt.date
    return df


def ic_by_group(df: pd.DataFrame, score: str, target: str, group: str | None = None) -> pd.DataFrame:
    rows = []
    groups = [(None, df)] if group is None else list(df.groupby(group, observed=True))
    for g, part in groups:
        ic = part.groupby("datetime")[[score, target]].apply(lambda x: x[score].corr(x[target], method="spearman") if len(x) >= 5 else np.nan).dropna()
        mu, t = nw_tstat(ic.to_numpy()) if len(ic) > 10 else (np.nan, np.nan)
        rows.append({"group": "all" if g is None else g, "n_obs": len(part), "days": len(ic), "rank_ic": mu, "t": t})
    return pd.DataFrame(rows)


def main() -> None:
    paths = load_paths()
    rets = returns_table(paths["qlib_dir"])
    src = source_share(paths)
    mcap = pl.read_parquet(paths["market_cap"], columns=["datetime", "instrument", "mcap"]).to_pandas()
    mcap["datetime"] = pd.to_datetime(mcap["datetime"]).dt.date
    preds = load_preds(Path(paths["pred_dir"]))
    md = ["# 信号去向拆分（主口径 Ridge 分数，2020–2023，日度 Rank IC 与 Newey–West t）", ""]
    for key in [k for k in FOCUS if k in preds]:
        label = f"{NAMES[key.split('__')[0]]} / {TEXT[key.split('__')[1]]}"
        s = preds[key].stack().rename("score").reset_index()
        s["datetime"] = pd.to_datetime(s["datetime"]).dt.date
        df = (s.merge(rets, on=["datetime", "instrument"], how="inner").merge(src, on=["datetime", "instrument"], how="left")
                .merge(mcap, on=["datetime", "instrument"], how="left"))
        md += [f"## {label}", "", "### 按收益窗口", "", "| 窗口 | Rank IC | t | 交易日 |", "| --- | ---: | ---: | ---: |"]
        for w in WINDOWS:
            r = ic_by_group(df.dropna(subset=[w]), "score", w).iloc[0]
            md.append(f"| {w} | {r.rank_ic:+.4f} | {r.t:+.2f} | {r.days} |")
        df["src_group"] = pd.cut(df["benzinga_share"].fillna(0), [-0.01, 0.0, 0.999, 1.0], labels=["全为 nasdaq.com 全文", "混合", "全为 Benzinga 标题"])
        df["cnt_group"] = pd.cut(df["news_cnt"].fillna(1), [0, 1, 3, 1e9], labels=["1 条", "2–3 条", "≥4 条"])
        df["abs_same"] = df["same_day"].abs()
        df["move_group"] = df.groupby("datetime")["abs_same"].transform(lambda x: pd.qcut(x.rank(method="first"), 3, labels=["小", "中", "大"]) if len(x) >= 6 else pd.Series(index=x.index, dtype=object))
        df["size_group"] = df.groupby("datetime")["mcap"].transform(lambda x: pd.qcut(x.rank(method="first"), 3, labels=["小", "中", "大"]) if x.notna().sum() >= 6 else pd.Series(index=x.index, dtype=object))
        for gname, gcol in [("按来源", "src_group"), ("按新闻条数", "cnt_group"), ("按当天 |收益| 三分位（日内）", "move_group"), ("按市值三分位（日内，S&P 500 内部）", "size_group")]:
            md += ["", f"### {gname}（主标签）", "", "| 子样本 | 股票-日 | 交易日 | Rank IC | t |", "| --- | ---: | ---: | ---: | ---: |"]
            for _, r in ic_by_group(df.dropna(subset=[gcol, "main_oo"]), "score", "main_oo", gcol).iterrows():
                md.append(f"| {r.group} | {r.n_obs:,} | {r.days} | {r.rank_ic:+.4f} | {r.t:+.2f} |")
        md.append("")
    res = ROOT / paths["results"] / "ridge"
    (res / "signal_decomposition.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
