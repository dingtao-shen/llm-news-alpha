"""表 A 初表：汇总 results/ridge/*__main.json → results/ridge/table_a.md（模型 × 文本类型，各测试年与全期的 Rank IC / IC）。

ChronoBERT 四个版本各只有一个测试年（(Y-1)1231 版本测 Y 年），拼成一行"chronobert（按年滚动）"。
全期指标用各测试年按交易日数加权平均。运行：python -m analysis.table_a
"""
from __future__ import annotations

import json
from pathlib import Path

from common import ROOT, load_paths
from models.labels import MAIN_LABEL

ORDER = ["llama3_base", "chronobert", "finbert", "minilm", "tfidf", "lm_dict"]
NAMES = {"llama3_base": "LLaMA3-8B", "chronobert": "ChronoBERT（按年滚动）", "finbert": "FinBERT", "minilm": "MiniLM",
         "tfidf": "TF-IDF（5,000 维）+ Ridge", "lm_dict": "LM 词典情绪分（无训练）"}
TEXT = {"title": "标题", "body": "原文", "summary": "摘要"}
YEARS = [2020, 2021, 2022, 2023]


def collect(res: Path) -> dict[tuple[str, str], dict[int, dict]]:
    rows: dict[tuple[str, str], dict[int, dict]] = {}
    for f in sorted(res.glob("*__main.json")):
        r = json.loads(f.read_text())
        model = "chronobert" if r["model"].startswith("chronobert-") else r["model"]
        for w in r["windows"]:
            rows.setdefault((model, r["text_type"]), {})[w["test_year"]] = {**w["labels"][MAIN_LABEL], "n_test": w["n_test"], "version": r["model"]}
    return rows


def weighted(ws: list[dict], key: str) -> float | None:
    pairs = [(w[key], w["test_days"]) for w in ws if key in w]
    return sum(v * d for v, d in pairs) / sum(d for _, d in pairs) if pairs else None


def main() -> None:
    paths = load_paths()
    res = ROOT / paths["results"] / "ridge"
    rows = collect(res)
    md = ["# 表 A 初表：文本表示 × 文本类型，全维年度滚动 Ridge，主口径（9:00 ET，开盘到开盘标签）", "",
          "测试期 2020–2023，每年 4 年训练 + 1 年验证 + 1 年测试，λ 在验证年按日均 Rank IC 选。全期列为各年按交易日数加权。",
          "ChronoBERT 测试第 Y 年用知识截止 (Y−1)-12-31 的版本，只嵌入该窗口 6 年。摘要 = LLaMA3-8B-Instruct 对原文（前 800 token）生成的 2–3 句摘要（v2 提示词），再用各模型嵌入，故 n_test 与原文列相同。", "",
          "| 模型 | 文本 | " + " | ".join(f"{y} Rank IC" for y in YEARS) + " | 全期 Rank IC | 全期 IC | 平均 Rank ICIR | n_test（合计） |",
          "| --- | --- |" + " ---: |" * (len(YEARS) + 4)]
    for model in ORDER:
        for text in ("title", "body", "summary"):
            ws = rows.get((model, text))
            if not ws:
                if text != "summary":
                    md.append(f"| {NAMES[model]} | {TEXT[text]} |" + " – |" * (len(YEARS) + 4))
                continue
            cells = [f"{ws[y]['test_rank_ic']:+.4f}" if y in ws else "–" for y in YEARS]
            wl = [ws[y] for y in YEARS if y in ws]
            md.append(f"| {NAMES[model]} | {TEXT[text]} | " + " | ".join(cells) +
                      f" | {weighted(wl, 'test_rank_ic'):+.4f} | {weighted(wl, 'test_ic'):+.4f} | {sum(w['test_rank_icir'] for w in wl) / len(wl):+.3f} | {sum(w['n_test'] for w in wl):,} |")
    md += ["", "## 验证年选出的 λ（相对 trace(S)/P）与验证 Rank IC", "",
           "| 模型 | 文本 | " + " | ".join(f"{y}: λ_rel / 验证 Rank IC" for y in YEARS) + " |", "| --- | --- |" + " ---: |" * len(YEARS)]
    for model in ORDER:
        for text in ("title", "body", "summary"):
            ws = rows.get((model, text))
            if ws and all(ws[y].get("lambda_rel") is not None for y in ws):
                md.append(f"| {NAMES[model]} | {TEXT[text]} | " + " | ".join(f"{ws[y]['lambda_rel']:.3g} / {ws[y]['val_rank_ic']:+.4f}" if y in ws else "–" for y in YEARS) + " |")
    (res / "table_a.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
