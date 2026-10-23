"""模块 3 任务 4：LLaMA3-8B-Instruct + vLLM 批量生成新闻摘要（第三种文本）。venv-vllm 运行。

- 输入：news_clean（接口文件 1）里有正文的记录；正文按分词器截到前 BODY_TOKENS 个 token 再喂模型（模板 + 输出留余量，max_model_len 4096）。
- 输出：paths.summaries_dir/<model>/part-NNNNN.parquet（news_id, summary, n_out_tokens），按 news_id 排序、每片 SHARD 条，已存在的分片跳过，
  先写 .tmp 再改名；_meta.json 记录提示词版本、解码参数、模型 commit。
- 提示词：模块 0 的旧版（PROMPT_V0）10 条里 3 条"加料"（补后果、补动机、写"未披露"）。新版（PROMPT_V1）明确禁止推断原因 / 后果 / 动机与评价，
  禁止写"未提及 / 未披露"，限 1–2 句，附 2 个示范。放量前用 --compare N 在真实新闻上并排输出两版供人工判断加料率。
- 解码：temperature 0（贪心）、max_tokens 96、seed 0。

试跑对比：bash infra/run_bg.sh summ-compare /workspace/venv-vllm/bin/python -m text.summarize_vllm --compare 50
放量：    bash infra/run_bg.sh summarize /workspace/venv-vllm/bin/python -m text.summarize_vllm
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import time
from pathlib import Path

os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")   # 本机没有 nvcc，FlashInfer 采样算子无法 JIT 编译
os.environ["OMP_NUM_THREADS"] = "4"                          # vLLM 推理时 torch CPU 线程过多会和 cgroup 配额相互干扰

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from common import ROOT, load_paths

SHARD = 20_000
BODY_TOKENS = 1500
MAX_TOKENS_OUT = 96

PROMPT_V0 = (
    "You summarize financial news about one company. Use only information stated in the article. "
    "Do not add facts, numbers, names, or context that are not in the article. Reply with 2-3 sentences."
)
PROMPT_V1 = """You write a one- or two-sentence summary of a financial news article about a company, for a quantitative dataset.

Rules:
1. State only what the article explicitly says happened. Copy the key facts: who, what, how much, when.
2. Do not infer or add causes, consequences, motives, expectations, or evaluations that the article does not state.
3. Do not comment on what the article omits. Never write phrases like "was not disclosed", "did not mention", or "no details were given".
4. No introductions ("The article says...", "In summary..."), no bullet points, no opinions. Keep names, tickers, and numbers exactly as written.
5. If the article is a list or a market roundup, summarize only the part about the company named by the ticker.

Example 1
Article: Acme Corp reported third-quarter earnings of $1.42 per share, above the $1.30 analysts expected. Revenue rose 12% to $8.1 billion, driven by smartphone sales. The company raised its full-year outlook.
Summary: Acme Corp reported third-quarter EPS of $1.42 versus the $1.30 expected, with revenue up 12% to $8.1 billion on smartphone sales, and raised its full-year outlook.

Example 2
Article: Umbrella Aerospace said its chief executive will step down at the end of the year. The board has begun a search for a successor.
Summary: Umbrella Aerospace's chief executive will step down at year-end and the board has started searching for a successor."""

PROMPTS = {"v0": PROMPT_V0, "v1": PROMPT_V1}
MODEL_KEY = "llama3_instruct"


def truncate_tokens(tok, text: str, n: int) -> str:
    ids = tok(text, add_special_tokens=False, truncation=True, max_length=n)["input_ids"]
    return tok.decode(ids)


def make_conv(prompt: str, ticker: str, title: str, body: str) -> list[dict]:
    return [{"role": "system", "content": prompt},
            {"role": "user", "content": f"Ticker: {ticker}\nHeadline: {title}\nArticle:\n{body}\n\nSummary:"}]


def load_llm(model_id: str):
    from vllm import LLM
    t0 = time.time()
    llm = LLM(model=model_id, dtype="bfloat16", max_model_len=4096, gpu_memory_utilization=0.85, seed=0, enable_prefix_caching=True)
    print(f"vLLM loaded {model_id} in {time.time() - t0:.0f}s", flush=True)
    return llm


def generate(llm, convs: list[list[dict]]) -> list[tuple[str, int]]:
    from vllm import SamplingParams
    sp = SamplingParams(temperature=0.0, max_tokens=MAX_TOKENS_OUT, seed=0)
    outs = llm.chat(convs, sp, use_tqdm=False)
    return [(o.outputs[0].text.strip(), len(o.outputs[0].token_ids)) for o in outs]


# ------------------------------------------------------------------ 加料的粗略自动线索（只是提示，最终以人工判断为准）
_NUM = re.compile(r"\$?\d[\d,\.]*%?")
_CAP = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")
_OMIT = re.compile(r"not (?:disclosed|mentioned|specified|provided|given|stated)|no (?:details|further|specific)|did not (?:say|disclose|provide|mention)|unspecified|undisclosed", re.I)


def extra_content_hints(summary: str, source: str) -> dict:
    src = source.lower()
    nums = [n for n in _NUM.findall(summary) if n.strip("$%.,") and n.lower().strip("$%") not in src.replace(",", "")]
    caps = [c for c in _CAP.findall(summary) if c.lower() not in src and c not in {"The", "In", "It", "Its", "This", "That", "On", "For", "With", "After"}]
    return {"new_numbers": nums, "new_names": caps, "omission_phrase": bool(_OMIT.search(summary)), "sentences": len(re.findall(r"[.!?](?:\s|$)", summary))}


def compare(n: int, paths: dict, seed: int = 0) -> None:
    from transformers import AutoTokenizer
    model_id = paths["models"]["llama3_instruct"]
    tok = AutoTokenizer.from_pretrained(model_id)
    df = (pl.scan_parquet(paths["news"]["clean"]).filter(pl.col("has_body") & pl.col("in_sp500")).select("news_id", "ticker", "title", "body", "source", "ts_et")
            .collect().sample(n, seed=seed))
    bodies = [truncate_tokens(tok, b, BODY_TOKENS) for b in df["body"]]
    llm = load_llm(model_id)
    res = {}
    for ver, prompt in PROMPTS.items():
        t0 = time.time()
        res[ver] = generate(llm, [make_conv(prompt, t, h, b) for t, h, b in zip(df["ticker"], df["title"], bodies)])
        print(f"{ver}: {n} summaries in {time.time() - t0:.1f}s", flush=True)
    md = [f"# 摘要提示词对比：旧版 v0 vs 新版 v1，{n} 条真实新闻（seed {seed}）", "",
          "自动线索只是提示：new_numbers / new_names = 摘要里出现、原文里没有的数字 / 大写词；omission = 出现"未披露"类措辞。请人工判断哪一版加料更少。", ""]
    agg = {v: {"omission": 0, "new_numbers": 0, "new_names": 0, "avg_sentences": 0.0, "avg_tokens": 0.0} for v in PROMPTS}
    for i in range(n):
        r = df.row(i, named=True)
        md += [f"## {i + 1}. [{r['ticker']}] {r['title']}", f"*{r['source']}, {r['ts_et'].date()}*", "", "> " + bodies[i][:700].replace("\n", " ") + (" …" if len(bodies[i]) > 700 else ""), ""]
        for ver in PROMPTS:
            text, ntok = res[ver][i]
            h = extra_content_hints(text, r["title"] + " " + bodies[i])
            agg[ver]["omission"] += h["omission_phrase"]; agg[ver]["new_numbers"] += bool(h["new_numbers"]); agg[ver]["new_names"] += bool(h["new_names"])
            agg[ver]["avg_sentences"] += h["sentences"] / n; agg[ver]["avg_tokens"] += ntok / n
            flags = " ".join(f for f, ok in (("⚠omission", h["omission_phrase"]), (f"⚠nums{h['new_numbers']}", h["new_numbers"]), (f"⚠names{h['new_names'][:3]}", h["new_names"])) if ok)
            md += [f"**{ver}** ({ntok} tok{', ' + flags if flags else ''}): {text}", ""]
    summary = ["## 汇总（自动线索）", "", "| 版本 | 出现\"未披露\"措辞 | 含原文没有的数字 | 含原文没有的大写词 | 平均句数 | 平均输出 token |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    summary += [f"| {v} | {a['omission']} | {a['new_numbers']} | {a['new_names']} | {a['avg_sentences']:.1f} | {a['avg_tokens']:.0f} |" for v, a in agg.items()]
    res_dir = ROOT / paths["results"] / "news"
    (res_dir / "summary_prompt_compare.md").write_text("\n".join(md[:4] + summary + [""] + md[4:]) + "\n")
    print("\n".join(summary))


def run_full(paths: dict, prompt_version: str, limit: int | None) -> None:
    from transformers import AutoTokenizer
    model_id = paths["models"]["llama3_instruct"]
    tok = AutoTokenizer.from_pretrained(model_id)
    out_dir = Path(paths["summaries_dir"]) / MODEL_KEY; out_dir.mkdir(parents=True, exist_ok=True)
    lf = pl.scan_parquet(paths["news"]["clean"]).filter(pl.col("has_body")).select("news_id", "ticker", "title", "body").sort("news_id")
    if limit:
        lf = lf.head(limit)
    df = lf.collect()
    n_shards = (len(df) + SHARD - 1) // SHARD
    todo = [i for i in range(n_shards) if not (out_dir / f"part-{i:05d}.parquet").exists()]
    print(f"{len(df):,} articles, {n_shards} shards, {len(todo)} to do; prompt {prompt_version}", flush=True)
    if not todo:
        return
    llm = load_llm(model_id)
    meta = {"model_id": model_id, "prompt_version": prompt_version, "prompt": PROMPTS[prompt_version], "temperature": 0.0, "max_tokens": MAX_TOKENS_OUT,
            "body_tokens": BODY_TOKENS, "shard": SHARD, "n_articles": len(df), "started_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    (out_dir / "_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    t_start = time.time()
    for k, i in enumerate(todo):
        part = df.slice(i * SHARD, SHARD)
        t0 = time.time()
        bodies = [truncate_tokens(tok, b, BODY_TOKENS) for b in part["body"]]
        outs = generate(llm, [make_conv(PROMPTS[prompt_version], t, h, b) for t, h, b in zip(part["ticker"], part["title"], bodies)])
        table = pa.table({"news_id": pa.array(part["news_id"].to_list(), pa.string()), "summary": pa.array([o[0] for o in outs], pa.string()),
                          "n_out_tokens": pa.array([o[1] for o in outs], pa.int32())})
        tmp = out_dir / f"part-{i:05d}.parquet.tmp"
        pq.write_table(table, tmp, compression="zstd"); os.replace(tmp, out_dir / f"part-{i:05d}.parquet")
        secs = time.time() - t0; n_out = sum(o[1] for o in outs)
        eta = (len(todo) - k - 1) * (time.time() - t_start) / (k + 1) / 60
        print(f"shard {i + 1}/{n_shards}: {len(part):,} articles, {n_out:,} out tokens, {secs:.0f}s ({len(part) / secs:.1f} art/s), eta {eta:.0f} min", flush=True)
    meta["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"); meta["wall_secs"] = round(time.time() - t_start)
    (out_dir / "_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print("done", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", type=int, default=None, metavar="N", help="在 N 条真实新闻上并排输出两版提示词的摘要")
    ap.add_argument("--prompt", default="v1", choices=list(PROMPTS))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    paths = load_paths()
    if args.compare:
        compare(args.compare, paths, args.seed)
    else:
        run_full(paths, args.prompt, args.limit)


if __name__ == "__main__":
    main()
