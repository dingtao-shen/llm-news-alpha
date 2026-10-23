"""模块 3 任务 3：LLaMA3-8B（任意 HF AutoModel）均值池化嵌入，按 news_id 分片写出，支持断点续跑。

输入：paths.news.embed_candidates（按 news_id 排序）。某种文本第一次运行时先生成输入表
  <emb_dir>/_inputs/<text_type>.parquet：news_id, text（title；或 title + "\\n" + body，正文先截到前 BODY_CHARS 字符），
  按 news_id 排序，行组 = shard_size；第 i 片 = 第 i 个行组（news_id 是哈希，所以每片都是随机样本）。
输出：<emb_dir>/<model>/<text_type>/part-NNNNN.parquet：news_id string, emb fixed_size_list<float16, H>（接口文件 2）；
  目录下 _meta.json 记录模型 commit、分词与池化设置。已存在的分片跳过；先写 .tmp 再 os.replace，不会留下半截分片。
分批：按 token 长度降序，批内 padding 到最长，len(batch) * max_len <= batch_tokens 且 len(batch) <= max_batch。
池化：最后一层隐状态按 attention_mask 做掩码平均（text/pooling.py，与 infra/smoke_embed.py 一致）；bf16 推理，float16 落盘。
下一片的分词在后台线程里与当前片的 GPU 计算重叠。

模型：--model 取 paths.yaml models 里的键（llama3_base、finbert、minilm）；ChronoBERT 用 --model chronobert --version YYYYMMDD
  （model id = chronobert_prefix + version，输出目录 chronobert-YYYYMMDD）。--years Y0 Y1 只嵌入 ts_utc 年份在 [Y0, Y1] 的记录
  （ChronoBERT 按年滚动：测试年 Y 用 (Y-1)1231 版本，只嵌入窗口 [Y-5, Y] 的 6 年），输入表名带年份后缀。
  原文 max_len：MiniLM 256（模型训练长度），其余 512；标题一律 128；摘要 160。BERT 类模型含 [CLS]/[SEP] 一起做均值池化。
  --text-type summary 读 summaries_dir/llama3_instruct 的摘要表（第三种文本）。

增量（--delta <tag>）：候选集里尚无嵌入的 news_id（对照该目录现有全部分片）写成输入表 _inputs/<text>_delta-<tag>.parquet，
  嵌入输出为 delta-<tag>-part-NNNNN.parquet，与原分片并存；聚合读目录下全部 *part-*.parquet。换数据源或补别名（BRK.B）后只嵌新来的新闻。

试跑：python -m text.embed --model llama3_base --text-type title --limit 2000 --out <dir> --verify-readback
放量：make embed（LLaMA3）/ make embed-small（FinBERT、MiniLM、ChronoBERT 四个版本）
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")   # 权重加载进度条不要刷日志
os.environ.setdefault("TOKENIZERS_PARALLELISM", "true")

import numpy as np
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from common import ROOT, load_paths, ncpu
from text.batching import make_batches, padded_tokens, shard_name

BODY_CHARS = 8000          # 512 token 约 2,000–2,500 字符；多留余量后再交给分词器截断
TITLE_MAX_LEN = 128
SUMMARY_MAX_LEN = 160            # 摘要 1–2 句，128 个输出 token 以内
BODY_MAX_LEN = {"minilm": 256}   # 其余模型 512
BODY_MAX_LEN_DEFAULT = 512
SEED = 0


# ------------------------------------------------------------------ 输入表
def existing_ids(out_dir: Path) -> set[str]:
    """该模型/文本目录下所有分片（含 delta）已有的 news_id。"""
    ids: set[str] = set()
    for f in out_dir.glob("*part-*.parquet"):
        ids.update(pq.read_table(f, columns=["news_id"])["news_id"].to_pylist())
    return ids


def build_inputs(candidates: Path, text_type: str, out: Path, shard_size: int, limit: int | None,
                 years: tuple[int, int] | None = None, exclude_ids: set[str] | None = None,
                 summaries_dir: Path | None = None) -> int:
    """从候选集生成 (news_id, text) 输入表，按 news_id 排序、行组 = shard_size。返回行数。
    years=(Y0, Y1) 只取该年份区间；exclude_ids 给定时只取其外的 news_id（增量）。"""
    lf = pl.scan_parquet(str(candidates))
    if years:
        lf = lf.filter(pl.col("ts_utc").dt.year().is_between(years[0], years[1]))
    if exclude_ids is not None:
        lf = lf.filter(~pl.col("news_id").is_in(list(exclude_ids)))
    if text_type == "title":
        lf = lf.select("news_id", pl.col("title").alias("text"))
    elif text_type == "body":
        lf = (lf.filter(pl.col("has_body"))
                .select("news_id", pl.concat_str([pl.col("title"), pl.lit("\n"), pl.col("body").str.slice(0, BODY_CHARS)]).alias("text")))
    elif text_type == "summary":
        # 第三种文本：LLaMA3-8B-Instruct 生成的摘要（text/summarize_vllm.py，summaries_dir/<model>/part-*.parquet），只对有摘要的记录
        sdir = summaries_dir or Path(load_paths()["summaries_dir"]) / "llama3_instruct"
        files = sorted(sdir.glob("part-*.parquet"))
        assert files, f"no summaries in {sdir}"
        # summary 列按写出当时的规则后处理；这里用 summary_raw + 最新的 clean_summary 重算（拒答 → 标题），规则更新不必重写分片
        from text.summarize_vllm import clean_summary
        summ = pl.concat([pl.scan_parquet(str(f)).select("news_id", "summary_raw") for f in files])
        lf = (lf.select("news_id", "title").join(summ, on="news_id", how="inner").sort("news_id")   # join 不保序，必须重排
                .select("news_id", pl.struct("summary_raw", "title").map_elements(
                    lambda s: clean_summary(s["summary_raw"], s["title"])[0], return_dtype=pl.String).alias("text")))
    else:
        raise ValueError(text_type)
    if limit:
        lf = lf.head(limit)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp.parquet")
    lf.sink_parquet(str(tmp), row_group_size=shard_size, maintain_order=True)
    ids = pl.scan_parquet(str(tmp)).select("news_id").collect()["news_id"]
    assert ids.is_sorted() and ids.n_unique() == len(ids), "input news_id must be sorted and unique"
    if len(ids) == 0:
        tmp.unlink(); return 0
    os.replace(tmp, out)
    return len(ids)


# ------------------------------------------------------------------ 模型
def local_commit(model_id: str) -> str | None:
    """HF 缓存里该模型 refs/main 指向的 commit（权重来自卷上的缓存，不联网）。"""
    from huggingface_hub.constants import HF_HUB_CACHE
    ref = Path(HF_HUB_CACHE) / f"models--{model_id.replace('/', '--')}" / "refs" / "main"
    return ref.read_text().strip() if ref.exists() else None


def load_model(model_id: str, dtype: str = "bf16"):
    import torch
    import transformers
    from transformers import AutoModel, AutoTokenizer
    transformers.logging.set_verbosity_error()
    assert torch.cuda.is_available(), "CUDA not available"
    torch.manual_seed(SEED)
    t0 = time.time()
    try:
        tok = AutoTokenizer.from_pretrained(model_id)
    except (ValueError, KeyError, OSError):
        # yiyanghkust/finbert-pretrain 只有 vocab.txt，config 没有 model_type / tokenizer_class；它就是 BERT 的 WordPiece 词表
        from transformers import BertTokenizerFast
        tok = BertTokenizerFast.from_pretrained(model_id)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token          # LLaMA 3 没有 pad token（与 smoke 一致）
    tok.padding_side = "right"
    torch_dtype = {"bf16": torch.bfloat16, "fp32": torch.float32}[dtype]
    try:
        model = AutoModel.from_pretrained(model_id, dtype=torch_dtype)
    except (ValueError, KeyError, OSError):
        # yiyanghkust/finbert-pretrain 的 config 没有 model_type，Auto 类推断不出架构；它就是 BERT
        from transformers import BertModel
        model = BertModel.from_pretrained(model_id, dtype=torch_dtype)
    model = model.to("cuda").eval()
    print(f"model {model_id} ({type(model).__name__}, {dtype}) loaded in {time.time() - t0:.1f}s, "
          f"gpu mem {torch.cuda.memory_allocated() / 1e9:.2f} GB, hidden {model.config.hidden_size}, commit {local_commit(model_id)}", flush=True)
    return tok, model


def tokenize(tok, texts: list[str], max_len: int) -> list[list[int]]:
    return tok(texts, add_special_tokens=True, truncation=True, max_length=max_len, padding=False,
               return_attention_mask=False)["input_ids"]


def embed_shard(model, ids: list[list[int]], pad_id: int, batch_tokens: int, max_batch: int,
                max_pad_ratio: float = 1.25) -> tuple[np.ndarray, dict]:
    import torch
    from text.pooling import masked_mean
    H = model.config.hidden_size
    lengths = [len(x) for x in ids]
    batches = make_batches(lengths, batch_tokens, max_batch, max_pad_ratio)
    out = np.empty((len(ids), H), dtype=np.float16)
    for b in batches:
        L = max(lengths[i] for i in b)
        arr = np.full((len(b), L), pad_id, dtype=np.int64)
        mask = np.zeros((len(b), L), dtype=np.int64)
        for r, i in enumerate(b):
            arr[r, :lengths[i]] = ids[i]
            mask[r, :lengths[i]] = 1
        input_ids = torch.from_numpy(arr).pin_memory().to("cuda", non_blocking=True)
        attn = torch.from_numpy(mask).pin_memory().to("cuda", non_blocking=True)
        with torch.inference_mode():
            h = model(input_ids=input_ids, attention_mask=attn).last_hidden_state
            pooled = masked_mean(h, attn).to(torch.float16)
        out[b] = pooled.cpu().numpy()
    torch.cuda.synchronize()
    return out, {"tokens": int(sum(lengths)), "padded_tokens": padded_tokens(lengths, batches), "batches": len(batches)}


def write_shard(path: Path, news_ids: list[str], emb: np.ndarray) -> None:
    flat = pa.array(emb.reshape(-1))                     # float16 -> halffloat
    col = pa.FixedSizeListArray.from_arrays(flat, emb.shape[1])
    table = pa.table({"news_id": pa.array(news_ids, pa.string()), "emb": col})
    tmp = path.with_suffix(".parquet.tmp")
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, path)


def verify_readback(path: Path, news_ids: list[str], emb: np.ndarray) -> dict:
    """用 pyarrow、polars、DuckDB 各读一遍，核对形状、dtype、数值。"""
    import duckdb
    res = {}
    t = pq.read_table(path)
    a = np.stack(t["emb"].to_numpy(zero_copy_only=False))
    res["pyarrow"] = {"dtype": str(a.dtype), "shape": list(a.shape), "ids_equal": t["news_id"].to_pylist() == news_ids,
                      "values_equal": bool(np.array_equal(a, emb))}
    d = pl.read_parquet(path)
    b = d["emb"].to_numpy()
    res["polars"] = {"dtype": str(d.schema["emb"]), "shape": list(b.shape), "ids_equal": d["news_id"].to_list() == news_ids,
                     "values_equal": bool(np.array_equal(b.astype(np.float16), emb))}
    rows = duckdb.connect().execute(f"SELECT news_id, emb FROM read_parquet('{path}')").fetchall()
    c = np.array([r[1] for r in rows], dtype=np.float32)
    res["duckdb"] = {"dtype": "FLOAT[] (halffloat 无损上转)", "shape": list(c.shape), "ids_equal": [r[0] for r in rows] == news_ids,
                     "values_equal": bool(np.array_equal(c, emb.astype(np.float32)))}
    res["all_ok"] = all(v["ids_equal"] and v["values_equal"] for v in res.values() if isinstance(v, dict))
    return res


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return None


# ------------------------------------------------------------------ 主流程
def main() -> None:
    import torch
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3_base", help="paths.yaml models 里的键，或 chronobert（配 --version）")
    ap.add_argument("--version", default=None, help="chronobert 的知识截止日 YYYYMMDD")
    ap.add_argument("--years", type=int, nargs=2, metavar=("Y0", "Y1"), default=None, help="只嵌入 ts_utc 年份在 [Y0, Y1] 的记录")
    ap.add_argument("--dtype", choices=["bf16", "fp32"], default="bf16")
    ap.add_argument("--text-type", choices=["title", "body", "summary"], required=True)
    ap.add_argument("--limit", type=int, default=None, help="只取前 N 条（试跑）")
    ap.add_argument("--out", default=None, help="输出根目录（默认 paths.emb_dir）；试跑时指向临时目录")
    ap.add_argument("--shard-size", type=int, default=50_000)
    ap.add_argument("--max-len", type=int, default=None)
    ap.add_argument("--batch-tokens", type=int, default=32_768, help="批内 padded token 预算；试跑 16k–64k 吞吐相同（约 9.9k tok/s），96k 反而变慢，32k 峰值显存 23.5 GB")
    ap.add_argument("--max-batch", type=int, default=1024)
    ap.add_argument("--max-pad-ratio", type=float, default=1.25, help="批内 padded/real token 上限")
    ap.add_argument("--verify-readback", action="store_true")
    ap.add_argument("--delta", default=None, metavar="TAG", help="只嵌入该目录尚无嵌入的 news_id，分片名 delta-<TAG>-part-NNNNN.parquet")
    args = ap.parse_args()

    if args.limit and not args.out:
        raise SystemExit("--limit 只用于试跑，必须同时指定 --out（否则会把截断的输入表写进正式 emb_dir）")
    paths = load_paths()
    if args.model == "chronobert":
        assert args.version and len(args.version) == 8, "chronobert 需要 --version YYYYMMDD"
        model_id, model_key = paths["models"]["chronobert_prefix"] + args.version, f"chronobert-{args.version}"
    else:
        model_id, model_key = paths["models"][args.model], args.model
    max_len = args.max_len or {"title": TITLE_MAX_LEN, "summary": SUMMARY_MAX_LEN}.get(args.text_type, BODY_MAX_LEN.get(args.model, BODY_MAX_LEN_DEFAULT))
    years = tuple(args.years) if args.years else None
    emb_root = Path(args.out or paths["emb_dir"])
    out_dir = emb_root / model_key / args.text_type
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(ncpu())

    suffix = f"_{years[0]}-{years[1]}" if years else ""
    prefix = f"delta-{args.delta}-" if args.delta else ""
    inputs = emb_root / "_inputs" / f"{args.text_type}{suffix}{'_delta-' + args.delta if args.delta else ''}.parquet"
    if not inputs.exists():
        t0 = time.time()
        exclude = existing_ids(out_dir) if args.delta else None
        n = build_inputs(Path(paths["news"]["embed_candidates"]), args.text_type, inputs, args.shard_size, args.limit, years, exclude)
        print(f"inputs {inputs}: {n:,} rows in {time.time() - t0:.1f}s" + (f" (excluded {len(exclude):,} existing)" if exclude is not None else ""), flush=True)
        if n == 0:
            print("nothing to embed"); return
    pf = pq.ParquetFile(inputs)
    n_shards, n_rows = pf.metadata.num_row_groups, pf.metadata.num_rows
    todo = [i for i in range(n_shards) if not (out_dir / (prefix + shard_name(i))).exists()]
    print(f"{model_key}/{args.text_type}{suffix}: {n_rows:,} rows, {n_shards} shards, {n_shards - len(todo)} done, {len(todo)} to do; "
          f"max_len={max_len} batch_tokens={args.batch_tokens} max_batch={args.max_batch}", flush=True)
    if not todo:
        return

    tok, model = load_model(model_id, args.dtype)
    meta = {
        "model_key": model_key, "model_id": model_id, "model_commit": local_commit(model_id), "years": years,
        "hidden_size": model.config.hidden_size, "model_class": type(model).__name__,
        "dtype_infer": {"bf16": "bfloat16", "fp32": "float32"}[args.dtype], "dtype_store": "float16",
        "pooling": "masked mean of last_hidden_state", "add_special_tokens": True, "padding_side": "right",
        "pad_token": tok.pad_token, "max_len": max_len, "text_type": args.text_type, "body_chars": BODY_CHARS,
        "shard_size": args.shard_size, "batch_tokens": args.batch_tokens, "max_batch": args.max_batch, "max_pad_ratio": args.max_pad_ratio,
        "inputs": str(inputs), "n_rows": n_rows, "n_shards": n_shards, "seed": SEED, "limit": args.limit,
        "transformers": __import__("transformers").__version__, "torch": torch.__version__,
        "code_commit": git_commit(), "started_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    meta_name = f"_meta{'-delta-' + args.delta if args.delta else ''}.json"
    (out_dir / meta_name).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")

    def load_and_tokenize(i: int):
        rg = pf.read_row_group(i, columns=["news_id", "text"])
        news_ids = rg["news_id"].to_pylist()
        texts = [t if t is not None else "" for t in rg["text"].to_pylist()]
        return news_ids, tokenize(tok, texts, max_len)

    pool = ThreadPoolExecutor(max_workers=1)
    fut = pool.submit(load_and_tokenize, todo[0])
    t_start, done_tokens, done_secs = time.time(), 0, 0.0
    for k, i in enumerate(todo):
        t0 = time.time()
        news_ids, ids = fut.result()
        t_tok = time.time() - t0
        if k + 1 < len(todo):
            fut = pool.submit(load_and_tokenize, todo[k + 1])
        torch.cuda.reset_peak_memory_stats()
        t1 = time.time()
        emb, st = embed_shard(model, ids, tok.pad_token_id, args.batch_tokens, args.max_batch, args.max_pad_ratio)
        t_gpu = time.time() - t1
        assert np.isfinite(emb.astype(np.float32)).all(), f"non-finite embeddings in shard {i}"
        write_shard(out_dir / (prefix + shard_name(i)), news_ids, emb)
        secs = time.time() - t0
        done_tokens += st["tokens"]; done_secs += t_gpu
        tps = st["tokens"] / t_gpu
        eta = (len(todo) - k - 1) * (done_secs / (k + 1)) / 60
        print(f"shard {i + 1}/{n_shards}  rows={len(ids):,}  tokens={st['tokens']:,}  padded={st['padded_tokens']:,}  "
              f"batches={st['batches']}  tok_wait={t_tok:.1f}s  gpu={t_gpu:.1f}s  total={secs:.1f}s  "
              f"{tps:,.0f} tok/s  peak_mem={torch.cuda.max_memory_allocated() / 1e9:.1f} GB  eta={eta:.1f} min", flush=True)
        if args.verify_readback and k == 0:
            print("readback:", json.dumps(verify_readback(out_dir / (prefix + shard_name(i)), news_ids, emb), ensure_ascii=False), flush=True)
    pool.shutdown()
    meta.update(finished_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                tokens_per_sec_overall=round(done_tokens / max(done_secs, 1e-9)), wall_secs=round(time.time() - t_start, 1))
    (out_dir / meta_name).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print(f"done {model_key}/{args.text_type}{suffix}: {len(todo)} shards, {done_tokens:,} tokens, {meta['tokens_per_sec_overall']:,} tok/s overall, "
          f"{meta['wall_secs']} s wall", flush=True)


if __name__ == "__main__":
    main()
