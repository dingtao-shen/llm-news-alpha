"""模块 0 验收：LLaMA3-8B 对 10 条文本输出 4096 维均值池化嵌入，并粗测吞吐。

运行：make smoke-embed（在 Pod 上，venv-main）
检查：
  1. 形状 (10, 4096)、数值有限；
  2. 单条与批量计算的嵌入一致（验证 padding 被正确屏蔽）；
  3. 语义近的句子更相近（粗略健全性，不作硬性断言）；
  4. 512 token 批量吞吐（tokens/s），用于修正模块 3 的耗时估算。
"""
import time

import torch
from transformers import AutoModel, AutoTokenizer

MODEL = "meta-llama/Meta-Llama-3-8B"
MAX_LEN = 512

TEXTS = [
    "Acme Corp beats quarterly earnings estimates as smartphone sales surge",            # 0
    "Acme Corp posts record profit, topping analyst expectations on strong phone demand",  # 1  ~0
    "Acme Corp misses revenue forecasts as smartphone shipments decline",                 # 2  opposite of 0
    "Northwind Energy shares fall after crude oil prices slump",                           # 3
    "Contoso Pharma wins FDA approval for its new cancer drug",                            # 4
    "Contoso Pharma's experimental drug fails late-stage clinical trial",                  # 5  opposite of 4
    "Fabrikam Bank raises its dividend and announces a $30 billion buyback",               # 6
    "Globex Motors recalls 2 million vehicles over driver-assist safety concerns",         # 7
    "Initech agrees to acquire a gaming studio in a $69 billion deal",                     # 8
    "Umbrella Aerospace CEO steps down amid ongoing safety crisis",                        # 9
]


def embed(model, tok, texts, max_len=MAX_LEN):
    batch = tok(texts, padding=True, truncation=True, max_length=max_len, return_tensors="pt").to(model.device)
    with torch.inference_mode():
        h = model(**batch).last_hidden_state.float()          # (B, T, 4096)
    m = batch["attention_mask"].unsqueeze(-1).float()
    return (h * m).sum(1) / m.sum(1)                          # masked mean pooling


def main():
    assert torch.cuda.is_available(), "CUDA not available"
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL)
    tok.pad_token = tok.eos_token          # LLaMA 3 没有 pad token
    tok.padding_side = "right"
    model = AutoModel.from_pretrained(MODEL, torch_dtype=torch.bfloat16).to("cuda").eval()
    print(f"load: {time.time() - t0:.1f}s  gpu mem: {torch.cuda.memory_allocated() / 1e9:.1f} GB")

    e = embed(model, tok, TEXTS)
    assert e.shape == (10, 4096), e.shape
    assert torch.isfinite(e).all()
    print(f"shape: {tuple(e.shape)}  mean L2 norm: {e.norm(dim=1).mean():.2f}")

    single = embed(model, tok, [TEXTS[3]])[0]
    c = torch.nn.functional.cosine_similarity(single, e[3], dim=0).item()
    print(f"single vs batched cosine: {c:.5f}  ({'OK' if c > 0.999 else 'CHECK PADDING MASK'})")

    # LLM 均值池化嵌入各向异性很强（原始余弦普遍 > 0.9），先去均值再看相对远近
    z = torch.nn.functional.normalize(e - e.mean(0, keepdim=True), dim=1)
    s = z @ z.T
    print(f"centered cosine  same story (0,1): {s[0, 1]:+.3f}   opposite (0,2): {s[0, 2]:+.3f}   "
          f"unrelated (0,7): {s[0, 7]:+.3f}")

    # 吞吐：32 条 × 512 token
    long_text = " ".join(TEXTS * 20)
    bench = [long_text] * 32
    embed(model, tok, bench)               # warm-up
    torch.cuda.synchronize()
    t1, n_iter = time.time(), 5
    for _ in range(n_iter):
        embed(model, tok, bench)
    torch.cuda.synchronize()
    dt = time.time() - t1
    tps = n_iter * 32 * MAX_LEN / dt
    print(f"throughput: {tps:,.0f} tokens/s  -> ~{1e6 * 450 / tps / 3600:.1f} h per 1M articles at 450 tokens")
    print(f"peak gpu mem: {torch.cuda.max_memory_allocated() / 1e9:.1f} GB")
    print("smoke-embed ok")


if __name__ == "__main__":
    main()
