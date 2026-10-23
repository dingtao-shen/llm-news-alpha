"""模块 3 任务 4：LLaMA3-8B-Instruct + vLLM 批量生成新闻摘要（第三种文本）。venv-vllm 运行。

- 输入：news_clean（接口文件 1）里有正文的记录；正文按分词器截到前 BODY_TOKENS=800 个 token 再喂模型（与 512 token 的原文嵌入窗口接近；max_model_len 4096）。
- 输出：paths.summaries_dir/<model>/part-NNNNN.parquet（news_id, summary, summary_raw, flag, n_out_tokens），按 news_id 排序、每片 SHARD 条，已存在的分片跳过，
  先写 .tmp 再改名；_meta.json 记录提示词版本、解码参数、模型 commit。
- 提示词：模块 0 的旧版（PROMPT_V0）10 条里 3 条"加料"（补后果、补动机、写"未披露"）。新版（PROMPT_V1）明确禁止推断原因 / 后果 / 动机与评价，
  禁止写"未提及 / 未披露"，限 1–2 句，附 2 个示范；v2 再加 ticker 与文章不符时的处理与禁止元句开头。放量前用 --compare N 在真实新闻上并排输出供人工判断加料率。
- 后处理 clean_summary：去掉 "Here is a summary…:" 元句；拒答（多为 FNSPID 挂错 ticker）用标题代替并记 flag=fallback_title。
- 解码：temperature 0（贪心）、max_tokens 128、seed 0。

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
BODY_TOKENS = 800            # 原文前 800 token（与 512 token 的原文嵌入窗口接近；1,500 时在热降频的 GPU 上 20k 篇一片要 40 分钟以上）
MAX_TOKENS_OUT = 128

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

# v2 = v1 + 两条针对 50 条对比里暴露的问题：FNSPID 的 ticker 与文章不符时不要评论不符（5/50 条写了"There is no article about X"），
# 以及不要以任何元句开头。
PROMPT_V2 = PROMPT_V1.replace(
    "5. If the article is a list or a market roundup, summarize only the part about the company named by the ticker.",
    "5. If the article covers several companies, focus on the part about the company named by the ticker. If that company is barely or not "
    "discussed, summarize the article's main subject instead; never remark that the company is not mentioned.\n"
    "6. Start directly with the first fact. Never begin with phrases like \"There is no\", \"No summary\", \"The article\", or \"Here is\".")
PROMPTS = {"v0": PROMPT_V0, "v1": PROMPT_V1, "v2": PROMPT_V2}
MODEL_KEY = "llama3_instruct"


def truncate_tokens(tok, text: str, n: int) -> str:
    ids = tok(text, add_special_tokens=False, truncation=True, max_length=n)["input_ids"]
    return tok.decode(ids)


def truncate_tokens_batch(tok, texts: list[str], n: int) -> list[str]:
    """批量版（fast tokenizer 多线程），20k 篇约 10 秒；逐篇循环要几分钟。"""
    ids = tok(texts, add_special_tokens=False, truncation=True, max_length=n)["input_ids"]
    return tok.batch_decode(ids)


def make_conv(prompt: str, ticker: str, title: str, body: str) -> list[dict]:
    return [{"role": "system", "content": prompt},
            {"role": "user", "content": f"Ticker: {ticker}\nHeadline: {title}\nArticle:\n{body}\n\nSummary:"}]


def convs_to_token_prompts(tok, convs: list[list[dict]]) -> list:
    """把对话渲染成 Llama 3 聊天模板字符串后批量分词，交给 llm.generate（绕过 vLLM 前端逐条模板渲染 + 分词的 Python 开销：
    实测 20k 篇时主进程 110% CPU、EngineCore 只有 30%，GPU 在等前端）。"""
    from vllm import TokensPrompt
    texts = [tok.apply_chat_template(c, tokenize=False, add_generation_prompt=True) for c in convs]
    ids = tok(texts, add_special_tokens=False)["input_ids"]      # 模板串已含 <|begin_of_text|>
    return [TokensPrompt(prompt_token_ids=i) for i in ids]


def load_llm(model_id: str):
    from vllm import LLM
    t0 = time.time()
    llm = LLM(model=model_id, dtype="bfloat16", max_model_len=4096, gpu_memory_utilization=0.85, seed=0, enable_prefix_caching=True)
    print(f"vLLM loaded {model_id} in {time.time() - t0:.0f}s", flush=True)
    return llm


def generate(llm, convs: list[list[dict]], tok=None) -> list[tuple[str, int]]:
    from vllm import SamplingParams
    sp = SamplingParams(temperature=0.0, max_tokens=MAX_TOKENS_OUT, seed=0)
    if tok is not None:
        outs = llm.generate(convs_to_token_prompts(tok, convs), sp, use_tqdm=False)
    else:
        outs = llm.chat(convs, sp, use_tqdm=False)
    return [(o.outputs[0].text.strip(), len(o.outputs[0].token_ids)) for o in outs]


# ------------------------------------------------------------------ 后处理：去元句、识别拒答
_PREAMBLE = re.compile(r"^(?:here is|here's)[^\n:]{0,80}:\s*", re.I)
_REFUSAL = re.compile(r"^(?:no summary|there is no|the (?:provided )?(?:article|text) (?:does not|doesn't|is not)|unfortunately|i cannot|i can't)", re.I)


MAX_EMPTY_RATE = 0.05        # 一片里空输出占比超过它就视为引擎已挂（2026-10-23 第 3 片在引擎被杀时写出 19,067 条空摘要）


def shard_ok(n_out_tokens: list[int], max_empty_rate: float = MAX_EMPTY_RATE) -> bool:
    """空输出（0 个 token）比例不超过阈值才允许落盘；否则抛错，让断点续跑重做这一片。"""
    if not n_out_tokens:
        return True
    return sum(n == 0 for n in n_out_tokens) / len(n_out_tokens) <= max_empty_rate


def clean_summary(text: str, title: str) -> tuple[str, str]:
    """返回 (summary, flag)。flag ∈ {ok, stripped_preamble, fallback_title}。
    - 以 "Here is a summary…:" 开头 → 去掉该元句；
    - 拒答（"No summary…"、"There is no article about X…"，多为 FNSPID 把文章挂错 ticker）→ 用标题代替，保证每条都有可嵌入的文本。"""
    t = text.strip()
    flag = "ok"
    m = _PREAMBLE.match(t)
    if m:
        t = t[m.end():].strip(); flag = "stripped_preamble"
    if not t or _REFUSAL.match(t):
        return title.strip(), "fallback_title"
    return t, flag


# ------------------------------------------------------------------ 加料的粗略自动线索（只是提示，最终以人工判断为准）
_NUM = re.compile(r"\$?\d[\d,\.]*%?")
_CAP = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")
_OMIT = re.compile(r"not (?:disclosed|mentioned|specified|provided|given|stated)|no (?:details|further|specific)|did not (?:say|disclose|provide|mention)|unspecified|undisclosed", re.I)


def extra_content_hints(summary: str, source: str) -> dict:
    src = source.lower()
    nums = [n for n in _NUM.findall(summary) if n.strip("$%.,") and n.lower().strip("$%") not in src.replace(",", "")]
    caps = [c for c in _CAP.findall(summary) if c.lower() not in src and c not in {"The", "In", "It", "Its", "This", "That", "On", "For", "With", "After"}]
    return {"new_numbers": nums, "new_names": caps, "omission_phrase": bool(_OMIT.search(summary)), "sentences": len(re.findall(r"[.!?](?:\s|$)", summary))}


def compare(n: int, paths: dict, seed: int = 0, versions: list[str] | None = None) -> None:
    prompts = {k: PROMPTS[k] for k in (versions or list(PROMPTS))}
    from transformers import AutoTokenizer
    model_id = paths["models"]["llama3_instruct"]
    tok = AutoTokenizer.from_pretrained(model_id)
    df = (pl.scan_parquet(paths["news"]["clean"]).filter(pl.col("has_body") & pl.col("in_sp500")).select("news_id", "ticker", "title", "body", "source", "ts_et")
            .collect().sample(n, seed=seed))
    bodies = [truncate_tokens(tok, b, BODY_TOKENS) for b in df["body"]]
    llm = load_llm(model_id)
    res = {}
    for ver, prompt in prompts.items():
        t0 = time.time()
        res[ver] = generate(llm, [make_conv(prompt, t, h, b) for t, h, b in zip(df["ticker"], df["title"], bodies)])
        print(f"{ver}: {n} summaries in {time.time() - t0:.1f}s", flush=True)
    md = [f"# 摘要提示词对比：{' vs '.join(prompts)}，{n} 条真实新闻（seed {seed}）", "",
          "自动线索只是提示：new_numbers / new_names = 摘要里出现、原文里没有的数字 / 大写词；omission = 出现「未披露」类措辞。请人工判断哪一版加料更少。", ""]
    agg = {v: {"omission": 0, "new_numbers": 0, "new_names": 0, "avg_sentences": 0.0, "avg_tokens": 0.0} for v in prompts}
    for i in range(n):
        r = df.row(i, named=True)
        md += [f"## {i + 1}. [{r['ticker']}] {r['title']}", f"*{r['source']}, {r['ts_et'].date()}*", "", "> " + bodies[i][:700].replace("\n", " ") + (" …" if len(bodies[i]) > 700 else ""), ""]
        for ver in prompts:
            text, ntok = res[ver][i]
            h = extra_content_hints(text, r["title"] + " " + bodies[i])
            agg[ver]["omission"] += h["omission_phrase"]; agg[ver]["new_numbers"] += bool(h["new_numbers"]); agg[ver]["new_names"] += bool(h["new_names"])
            agg[ver]["avg_sentences"] += h["sentences"] / n; agg[ver]["avg_tokens"] += ntok / n
            flags = " ".join(f for f, ok in (("⚠omission", h["omission_phrase"]), (f"⚠nums{h['new_numbers']}", h["new_numbers"]), (f"⚠names{h['new_names'][:3]}", h["new_names"])) if ok)
            md += [f"**{ver}** ({ntok} tok{', ' + flags if flags else ''}): {text}", ""]
    summary = ["## 汇总（自动线索）", "", "| 版本 | 出现「未披露」措辞 | 含原文没有的数字 | 含原文没有的大写词 | 平均句数 | 平均输出 token |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    summary += [f"| {v} | {a['omission']} | {a['new_numbers']} | {a['new_names']} | {a['avg_sentences']:.1f} | {a['avg_tokens']:.0f} |" for v, a in agg.items()]
    res_dir = ROOT / paths["results"] / "news"
    (res_dir / f"summary_prompt_compare_{'_'.join(prompts)}.md").write_text("\n".join(md[:4] + summary + [""] + md[4:]) + "\n")
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
        bodies = truncate_tokens_batch(tok, [b or "" for b in part["body"]], BODY_TOKENS)
        outs = generate(llm, [make_conv(PROMPTS[prompt_version], t, h, b) for t, h, b in zip(part["ticker"], part["title"], bodies)], tok)
        cleaned = [clean_summary(o[0], h) for o, h in zip(outs, part["title"])]
        if not shard_ok([o[1] for o in outs]):
            raise RuntimeError(f"shard {i + 1}: {sum(o[1] == 0 for o in outs)} empty generations out of {len(outs)}; engine probably dead, not writing")
        table = pa.table({"news_id": pa.array(part["news_id"].to_list(), pa.string()),
                          "summary": pa.array([c[0] for c in cleaned], pa.string()),
                          "summary_raw": pa.array([o[0] for o in outs], pa.string()),
                          "flag": pa.array([c[1] for c in cleaned], pa.string()),
                          "n_out_tokens": pa.array([o[1] for o in outs], pa.int32())})
        tmp = out_dir / f"part-{i:05d}.parquet.tmp"
        pq.write_table(table, tmp, compression="zstd"); os.replace(tmp, out_dir / f"part-{i:05d}.parquet")
        secs = time.time() - t0; n_out = sum(o[1] for o in outs); n_fb = sum(c[1] == "fallback_title" for c in cleaned); n_st = sum(c[1] == "stripped_preamble" for c in cleaned)
        eta = (len(todo) - k - 1) * (time.time() - t_start) / (k + 1) / 60
        print(f"shard {i + 1}/{n_shards}: {len(part):,} articles, {n_out:,} out tokens, {secs:.0f}s ({len(part) / secs:.1f} art/s), "
              f"fallback {n_fb} stripped {n_st}, eta {eta:.0f} min", flush=True)
    meta["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"); meta["wall_secs"] = round(time.time() - t_start)
    (out_dir / "_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print("done", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", type=int, default=None, metavar="N", help="在 N 条真实新闻上并排输出两版提示词的摘要")
    ap.add_argument("--prompt", default="v2", choices=list(PROMPTS))
    ap.add_argument("--versions", nargs="+", default=None, help="--compare 时只比较这些版本")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    paths = load_paths()
    if args.compare:
        compare(args.compare, paths, args.seed, args.versions)
    else:
        run_full(paths, args.prompt, args.limit)


if __name__ == "__main__":
    main()
