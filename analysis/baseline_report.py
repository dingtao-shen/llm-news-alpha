"""模块 1 任务 7：从 MLflow 记录里取出 qrun 基线的 IC 与回测指标，写 results/baseline/<exp>.md、.json 与累计收益图。

读 recorder 的 metrics（SigAnaRecord：IC/ICIR/Rank IC/Rank ICIR）、`port_analysis_1day.pkl`（PortAnaRecord 的年化收益、信息比率、最大回撤等）
与 `report_normal_1day.pkl`（逐日收益、基准、成本、换手），画出多头组合与基准的累计收益、超额收益（含成本）。
运行：python -m analysis.baseline_report --exp baseline_alpha158_lgb [--rid <recorder id>]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import qlib
from qlib.constant import REG_US
from qlib.workflow import R

from common import ROOT, load_paths


def latest_recorder(exp_name: str, rid: str | None):
    exp = R.get_exp(experiment_name=exp_name, create=False)
    if rid:
        return exp.get_recorder(recorder_id=rid)
    recs = exp.list_recorders(rtype=exp.RT_L)
    recs = [r for r in recs if r.status == "FINISHED"] or recs
    return sorted(recs, key=lambda r: r.info["end_time"] or "")[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", default="baseline_alpha158_lgb")
    ap.add_argument("--rid", default=None)
    args = ap.parse_args()
    paths = load_paths()
    qlib.init(provider_uri=paths["qlib_dir"], region=REG_US,
              exp_manager={"class": "MLflowExpManager", "module_path": "qlib.workflow.expm",
                           "kwargs": {"uri": paths["mlruns"] if str(paths["mlruns"]).startswith("file:") else f"file:{paths['mlruns']}",
                                      "default_exp_name": "Experiment"}})
    rec = latest_recorder(args.exp, args.rid)
    metrics = rec.list_metrics()
    port = rec.load_object("portfolio_analysis/port_analysis_1day.pkl")
    report = rec.load_object("portfolio_analysis/report_normal_1day.pkl")
    out = ROOT / paths["results"] / "baseline"; out.mkdir(parents=True, exist_ok=True)

    ic = {k: round(float(v), 4) for k, v in metrics.items() if k in ("IC", "ICIR", "Rank IC", "Rank ICIR")}
    pa = port["risk"] if isinstance(port, pd.DataFrame) and "risk" in port.columns else port
    rows = {"/".join(map(str, idx)) if isinstance(idx, tuple) else str(idx): round(float(v), 4) for idx, v in pa.items()}
    ret, bench = report["return"], report["bench"]
    excess_c = ret - report["cost"] - bench
    cum = pd.DataFrame({"portfolio (after cost)": (1 + ret - report["cost"]).cumprod() - 1,
                        "SPY": (1 + bench).cumprod() - 1,
                        "excess (after cost)": excess_c.cumsum()})
    fig, ax = plt.subplots(figsize=(9, 4.5))
    cum.plot(ax=ax); ax.set_title(f"{args.exp}: Top-50 long-only, open-to-open, 10 bps per round trip")
    ax.axhline(0, color="k", lw=0.5); ax.set_ylabel("cumulative return"); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(out / f"{args.exp}_cum_return.png", dpi=130); plt.close(fig)

    by_year = pd.DataFrame({"excess_after_cost": excess_c.groupby(excess_c.index.year).sum(),
                            "turnover": report["turnover"].groupby(report.index.year).mean(),
                            "portfolio": ret.groupby(ret.index.year).sum(), "SPY": bench.groupby(bench.index.year).sum()}).round(4)
    md = [f"# {args.exp}（qrun 基线）", "",
          f"- recorder {rec.id}，实验 {args.exp}；测试期 {ret.index[0].date()} 至 {ret.index[-1].date()}，{len(ret)} 个交易日",
          f"- 信号：IC {ic.get('IC')}、ICIR {ic.get('ICIR')}、Rank IC {ic.get('Rank IC')}、Rank ICIR {ic.get('Rank ICIR')}（日均截面相关，标签为开盘到开盘）",
          "", "## 回测（TopkDropout 50/5，deal_price open，单边 5 bps，基准 SPY）", "", "| 指标 | 值 |", "| --- | ---: |"]
    md += [f"| {k} | {v} |" for k, v in rows.items()]
    md += ["", "## 按年（收益为日收益简单求和）", "", "| 年 | 组合 | SPY | 超额（扣费） | 日均换手 |", "| --- | ---: | ---: | ---: | ---: |"]
    md += [f"| {y} | {r.portfolio:.2%} | {r.SPY:.2%} | {r.excess_after_cost:.2%} | {r.turnover:.3f} |" for y, r in by_year.iterrows()]
    md += ["", f"![cum]({args.exp}_cum_return.png)"]
    (out / f"{args.exp}.md").write_text("\n".join(md) + "\n")
    (out / f"{args.exp}.json").write_text(json.dumps({"recorder": rec.id, "metrics": {k: float(v) for k, v in metrics.items()},
                                                      "port_analysis": rows, "by_year": by_year.reset_index().to_dict("records")},
                                                     indent=2, default=str) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
