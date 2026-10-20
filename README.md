# llm-news-alpha

Replicating *Expected Returns and Large Language Models* (Chen, Kelly & Xiu) on free data:
FNSPID news → LLaMA3-8B / ChronoBERT embeddings → rolling full-dimension Ridge → next-day cross-sectional
return forecasts for S&P 500 point-in-time constituents (2015–2023, out-of-sample 2020–2023) →
quintile long-short backtests with costs, plus an incremental test against Qlib Alpha158.

> Work in progress. Status: module 0 (environment).

## Layout

```text
infra/      RunPod bootstrap, env, smoke tests, background-job helper
data/       universe, prices, market cap, Qlib dump            (module 1)
news/       FNSPID parsing, stats, timezone check, filters, alignment   (module 2)
text/       embeddings, vLLM summaries, bag-of-words baselines (module 3)
models/     sufficient-statistics Ridge, PCA export            (module 3)
qlib_ext/   custom Handler and Model wrappers                  (module 4)
configs/    Qlib workflow YAMLs                                (modules 1, 4)
analysis/   long-short, costs, decay, size, text type          (module 6)
tests/      pytest on small samples (runs on a laptop)
results/    small tables and figures
docs/       worklog
```

## Compute

All computation runs on one fixed RunPod configuration (1 × L40S 48GB, Secure Cloud, 250 GB network volume);
see `infra/runpod_template.md`. Development happens locally with Claude Code; experiments run on the Pod.

## Data and licenses

FNSPID (CC BY-NC 4.0 per its Hugging Face card) is used for research only; this repository does not
redistribute news text or generated summaries. LLaMA 3 is used under the Meta Llama 3 Community License.
