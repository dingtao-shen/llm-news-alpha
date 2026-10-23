"""λ 口径敏感性：验证年选 λ（results/ridge/*__main.json）vs 固定 λ_rel（*__main__lam<值>.json），主标签日均 Rank IC 对照表。
运行：python -m analysis.lambda_sensitivity [--lam 10] → results/ridge/lambda_sensitivity.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis.table_a import NAMES, ORDER, TEXT, YEARS, weighted
from common import ROOT, load_paths
from models.labels import MAIN_LABEL


def collect(res: Path, suffix: str) -> dict:
    rows: dict = {}
    for f in sorted(res.glob(f"*__main{suffix}.json")):
        r = json.loads(f.read_text()); model = "chronobert" if r["model"].startswith("chronobert-") else r["model"]
        for w in r["windows"]:
            rows.setdefault((model, r["text_type"]), {})[w["test_year"]] = {**w["labels"][MAIN_LABEL], "n_test": w["n_test"]}
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--lam", default="10"); args = ap.parse_args()
    res = ROOT / load_paths()["results"] / "ridge"
    sel, fix = collect(res, ""), collect(res, f"__lam{args.lam}")
    md = [f"# λ 口径敏感性：验证年选 λ vs 固定 λ_rel = {args.lam}（主标签，日均 Rank IC）", "",
          "| 模型 | 文本 | " + " | ".join(f"{y} 选/固定" for y in YEARS) + " | 全期 选 | 全期 固定 |", "| --- | --- |" + " ---: |" * (len(YEARS) + 2)]
    wins = total = 0
    for m in ORDER:
        for t in ("title", "body"):
            a, b = sel.get((m, t)), fix.get((m, t))
            if not a or not b:
                continue
            ys = [y for y in YEARS if y in a and y in b]
            wa, wb = weighted([a[y] for y in ys], "test_rank_ic"), weighted([b[y] for y in ys], "test_rank_ic")
            wins += wb > wa; total += 1
            md.append(f"| {NAMES[m]} | {TEXT[t]} | " + " | ".join(f"{a[y]['test_rank_ic']:+.4f} / {b[y]['test_rank_ic']:+.4f}" for y in ys) + f" | {wa:+.4f} | {wb:+.4f} |")
    md += ["", f"固定 λ 的全期 Rank IC 高于验证选 λ 的组合：{wins} / {total}。验证年选出的 λ 在网格两端跳动、验证 IC 曲线平坦，λ 选择基本是噪声；",
           "正式口径建议预先固定 λ（或用多年验证平均），注意事后按测试结果挑固定值本身有轻微前视。"]
    (res / "lambda_sensitivity.md").write_text("\n".join(md) + "\n"); print("\n".join(md))


if __name__ == "__main__":
    main()
