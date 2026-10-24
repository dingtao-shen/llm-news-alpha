"""图 4：时间一致模型对照——按测试年拆分的日均 Rank IC（主口径，主标签）。

只读 results/ridge/<model>__<text>__main[__lam10].json（Pod 上 models/ridge_suffstats 的产出），不碰 /workspace，Mac 上可跑：
    python -m analysis.fig_time_consistency
输出 results/ridge/fig4_time_consistency.png 与同名 .md（图中数字的表格形式）。

ChronoBERT 是四个按年滚动的版本（测试第 Y 年用知识截止 (Y−1)-12-31 的权重），每个版本一个 json，这里拼成一条按年序列；
其余模型一个 json 里有四个测试年。固定 λ 行（__lam10）用于说明验证选 λ 的噪声如何影响单年数字。
"""
from __future__ import annotations

import json
from pathlib import Path

RES = Path(__file__).resolve().parents[1] / "results" / "ridge"
YEARS = [2020, 2021, 2022, 2023]
TEXTS = [("body", "原文"), ("title", "标题")]
# 固定顺序、固定颜色（dataviz 调色板前四槽，已过 CVD 校验）；时间一致的 ChronoBERT 放第一位
MODELS = [
    ("chronobert", "ChronoBERT（按年滚动，截止 Y−1 年底）", "#2a78d6"),
    ("llama3_base", "LLaMA3-8B（截止 2023-03，覆盖测试期）", "#eb6834"),
    ("finbert", "FinBERT（finbert-pretrain，2020 年发布）", "#1baf7a"),
    ("minilm", "MiniLM（all-MiniLM-L6-v2，2021 年发布）", "#eda100"),
]
LAMBDAS = [("", "验证年选 λ（主口径）"), ("__lam10", "固定 λ_rel = 10")]


def _json_path(model: str, text: str, suffix: str, year: int) -> Path:
    name = f"chronobert-{year - 1}1231" if model == "chronobert" else model
    return RES / f"{name}__{text}__main{suffix}.json"


def yearly_rank_ic(model: str, text: str, suffix: str) -> dict[int, float]:
    """每个测试年的主标签 Rank IC；ChronoBERT 从四个版本各取自己的测试年。"""
    out: dict[int, float] = {}
    for y in YEARS:
        d = json.loads(_json_path(model, text, suffix, y).read_text())
        w = next(w for w in d["windows"] if w["test_year"] == y)
        out[y] = w["labels"]["ret_oo"]["test_rank_ic"]
    return out


def overall_rank_ic(model: str, text: str, suffix: str) -> float:
    """全期日均 Rank IC（按交易日数加权）。ChronoBERT 由四个版本的 test_days 加权。"""
    num = den = 0.0
    for y in YEARS:
        d = json.loads(_json_path(model, text, suffix, y).read_text())
        w = next(w for w in d["windows"] if w["test_year"] == y)
        lab = w["labels"]["ret_oo"]
        num += lab["test_rank_ic"] * lab["test_days"]; den += lab["test_days"]
    return num / den


def collect() -> dict[tuple[str, str, str], dict[str, float]]:
    table = {}
    for suffix, _ in LAMBDAS:
        for text, _ in TEXTS:
            for model, _, _ in MODELS:
                row = {str(y): v for y, v in yearly_rank_ic(model, text, suffix).items()}
                row["全期"] = overall_rank_ic(model, text, suffix)
                table[(suffix, text, model)] = row
    return table


def plot(table: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    plt.rcParams["font.family"] = ["Heiti TC", "PingFang SC", "Arial Unicode MS", "DejaVu Sans"]
    cats = [str(y) for y in YEARS] + ["全期"]
    n = len(MODELS); width = 0.8 / n
    fig, axes = plt.subplots(len(LAMBDAS), len(TEXTS), figsize=(12, 7), sharey=True)
    for i, (suffix, lam_label) in enumerate(LAMBDAS):
        for j, (text, text_label) in enumerate(TEXTS):
            ax = axes[i, j]
            for k, (model, _, color) in enumerate(MODELS):
                vals = [table[(suffix, text, model)][c] for c in cats]
                xs = [c_i + (k - (n - 1) / 2) * width for c_i in range(len(cats))]
                ax.bar(xs, vals, width=width * 0.92, color=color, linewidth=0)
            ax.axhline(0, color="#777", linewidth=0.8)
            ax.axvline(len(cats) - 1.5, color="#bbb", linewidth=0.8, linestyle=":")
            ax.set_xticks(range(len(cats))); ax.set_xticklabels(cats)
            ax.set_title(f"{text_label} · {lam_label}", fontsize=11, loc="left")
            ax.grid(axis="y", color="#e5e5e5", linewidth=0.6); ax.set_axisbelow(True)
            for s in ("top", "right"): ax.spines[s].set_visible(False)
            if j == 0: ax.set_ylabel("日均 Rank IC")
    fig.legend(handles=[Patch(color=c, label=l) for _, l, c in MODELS], loc="lower center", ncol=2, frameon=False, fontsize=9)
    fig.suptitle("图 4 · 时间一致模型对照：按测试年拆分的日均 Rank IC（9:00 ET 截止，t+1 开盘→t+2 开盘标签，2020–2023）", fontsize=12)
    fig.tight_layout(rect=(0, 0.08, 1, 0.96)); fig.savefig(out, dpi=130); plt.close(fig)


def write_md(table: dict, out: Path) -> None:
    cats = [str(y) for y in YEARS] + ["全期"]
    lines = ["# 图 4 的数据：按测试年拆分的日均 Rank IC（主口径、主标签）", "",
             "数据来自 `results/ridge/<model>__<text>__main[__lam10].json`；ChronoBERT 四个滚动版本各取自己的测试年，全期按交易日数加权。", ""]
    for suffix, lam_label in LAMBDAS:
        for text, text_label in TEXTS:
            lines += [f"## {text_label} · {lam_label}", "", "| 模型 | " + " | ".join(cats) + " |", "| --- | " + " | ".join("---:" for _ in cats) + " |"]
            for model, label, _ in MODELS:
                row = table[(suffix, text, model)]
                lines.append(f"| {label} | " + " | ".join(f"{row[c]:+.4f}" for c in cats) + " |")
            lines.append("")
    lines.append("![fig4](fig4_time_consistency.png)")
    out.write_text("\n".join(lines) + "\n")


def main() -> None:
    table = collect()
    plot(table, RES / "fig4_time_consistency.png")
    write_md(table, RES / "fig4_time_consistency.md")
    print(f"wrote {RES / 'fig4_time_consistency.png'} and .md")


if __name__ == "__main__":
    main()
