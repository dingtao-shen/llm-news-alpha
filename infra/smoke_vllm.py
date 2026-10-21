"""模块 0 验收：LLaMA3-8B-Instruct + vLLM 对 10 篇短新闻生成摘要，并粗测生成吞吐。

运行：make smoke-vllm（在 Pod 上，venv-vllm）
"""
import os
import time

# FlashInfer 采样算子需要现场编译（本机没有 nvcc），改用 PyTorch 实现；贪心解码不受影响
os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
# vLLM 推理时 torch CPU 线程过多会和 cgroup 配额相互干扰
os.environ["OMP_NUM_THREADS"] = "4"

from vllm import LLM, SamplingParams

MODEL = "meta-llama/Meta-Llama-3-8B-Instruct"

SYSTEM = (
    "You summarize financial news about one company. Use only information stated in the article. "
    "Do not add facts, numbers, names, or context that are not in the article. Reply with 2-3 sentences."
)

ARTICLES = [
    "Acme Corp reported third-quarter earnings of $1.42 per share, above the $1.30 analysts expected. "
    "Revenue rose 12% to $8.1 billion, driven by smartphone sales. The company raised its full-year outlook.",
    "Northwind Energy shares fell 6% on Tuesday after crude prices dropped to a three-month low. "
    "The company said lower prices could reduce fourth-quarter cash flow.",
    "Contoso Pharma said the FDA approved its drug Velantib for advanced lung cancer. "
    "The company expects to begin shipping the drug in the United States next month.",
    "Contoso Pharma said its experimental Alzheimer's treatment failed to meet its primary endpoint "
    "in a Phase 3 trial. The company will stop development of the drug.",
    "Fabrikam Bank raised its quarterly dividend to $1.15 from $1.00 and approved a $30 billion "
    "share repurchase program after passing the annual stress test.",
    "Globex Motors is recalling about 2 million vehicles to update driver-assist software after a "
    "regulator raised safety concerns. The fix will be delivered over the air.",
    "Initech agreed to buy a video game studio for $69 billion in cash. The deal needs regulatory "
    "approval and is expected to close next year.",
    "Umbrella Aerospace said its chief executive will step down at the end of the year. "
    "The board has begun a search for a successor.",
    "Wayne Retail cut its annual sales forecast, citing weaker consumer spending on discretionary items. "
    "The company also said it would close 40 underperforming stores.",
    "Stark Semiconductor did not change its guidance but said demand for data-center chips remains "
    "strong. The company did not provide new financial targets.",
]


def main():
    t0 = time.time()
    llm = LLM(model=MODEL, dtype="bfloat16", max_model_len=4096, gpu_memory_utilization=0.85, seed=0)
    print(f"load: {time.time() - t0:.1f}s")

    sp = SamplingParams(temperature=0.0, max_tokens=160)
    convs = [[{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Article:\n" + a}]
             for a in ARTICLES]

    t1 = time.time()
    outs = llm.chat(convs, sp, use_tqdm=False)
    dt = time.time() - t1

    n_out = sum(len(o.outputs[0].token_ids) for o in outs)
    for i, o in enumerate(outs):
        print(f"\n[{i}] {o.outputs[0].text.strip()}")
    print(f"\n10 summaries in {dt:.1f}s  ({n_out / dt:,.0f} generated tokens/s at batch 10; "
          f"real throughput at large batch will be much higher)")
    print("smoke-vllm ok")


if __name__ == "__main__":
    main()
