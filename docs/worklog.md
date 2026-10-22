# Worklog

新条目写在最上面。每条：做了什么 / 产出在哪 / 下一步 / 遗留问题。

## 2026-10-22 · 模块 1 任务 1、模块 2 任务 1–2、嵌入候选集、LLaMA3-8B 嵌入启动

- 做了什么：
  - 时点成分股：`shardul0701/SP500-Survivorship-bias-data-2004-2026`（commit 40a9ddc）2015–2023 YAML 拷进 `data/universe_src/`，
    `data/build_universe.py` 回放成区间 → 716 个 ticker、723 个区间、2015-01-01 499 只、2023-12-31 503 只，逐年连续性一致；FB/META、GOOG/GOOGL 都保留。
  - FNSPID：两个 CSV 下载校验通过（23.2 GB + 5.7 GB，约 5 分钟），DuckDB 全字符串解析 28.6M 行只拒 1 行，三种解析器在 20 万行以上的头部对比完全一致。
    news_id 定义固定：`sha256(norm_url + "\n" + norm_title)` 前 24 位十六进制（`news/news_id.py`，plan.md 3.1）。
  - 来源统计（`results/news/fnspid_parse_report.md`）：All_external 是 nasdaq 文件的真子集（逐行相同），流水线只用 nasdaq 文件；
    带 ticker 的行 5.74M，其中有时刻的只有 1.4%；正文全部来自 nasdaq.com，2021–2023 只剩 nasdaq.com。详见 plan.md 新增 3.2 节。
  - 嵌入候选集（`news/candidates.py`）：505,147 条，其中有正文 270,049 条；单一股票规则剔掉 62% 的 S&P 行（422,101 篇多 ticker 文章，核实为同一篇挂多 ticker、不是 news_id 碰撞）；
    有时刻的只剩 2,511 行；FNSPID 按 ticker 的时间覆盖很不均匀（AAPL 只从 2020-03 起、MSFT 只从 2022-04 起、无 META）；`BRK` 写法未匹配 `BRK.B`。
  - `text/embed.py`：按 news_id 排序的输入表、行组 = 分片（5 万）、token 预算分批 + padding 比上限 1.25、float16 parquet 分片、断点续跑、三种读回校验。
    试跑：标题 8.3k tok/s / 17.7 GB，原文 9.9k tok/s / 23.5 GB（32k 预算；16k–64k 吞吐持平，96k 变慢）。
  - 正式嵌入已用 run_bg 启动（`make embed`，job `embed-llama3_base`，日志 `/workspace/logs/embed-llama3_base_20261022_161651.log`）：先标题全集（11 片，约 18 分钟），再原文子集（6 片，约 3.5 小时）。首片 5 万条实测 9,933 tok/s、padding 比 1.03、峰值 23.5 GB；之后 GPU 热降频（88–89 °C，SM 840–1170 MHz，throttle reason SW thermal slowdown），稳定在约 6.2–6.5k tok/s。标题全集 16:41 UTC 完成：11 片、8,853,188 token、6,543 tok/s、24 分钟。原文首片 62.7 分钟（6,159 tok/s），6 片预计约 23:00 UTC 完成；**在此之前不要 Terminate Pod**。
- 产出在哪：
  - `/workspace/qlib_data/us_sp500/instruments/sp500.txt`、`/workspace/data/raw/universe/sp500_membership.parquet`、`results/universe/`
  - `/workspace/data/raw/fnspid/{nasdaq_exteral_data.csv,All_external.csv,MANIFEST.json}`、`/workspace/data/news/fnspid_parquet/{nasdaq,all_external}/`
  - `/workspace/data/news/embed_candidates.parquet`（+ `_meta.json`）、`results/news/`
  - `/workspace/data/emb/_inputs/{title,body}.parquet`、`/workspace/data/emb/llama3_base/{title,body}/part-*.parquet`（+ `_meta.json`）
- 分片按 news_id（哈希）排序，所以每个已完成的分片都是候选集的随机样本：嵌入全部完成之前就可以拿前几片试跑 Ridge。
- 下一步：
  - 嵌入跑完后核对分片数（标题 11、原文 6）、`_meta.json` 的 tokens_per_sec_overall，并把吞吐实测写进 plan.md 5.5 节。
  - 模块 2 任务 3–9：时区校验重心改为"仅日期记录的日期可靠性"（见 plan.md 3.2）；ticker 映射加 `BRK → BRK.B`；长度与近似重复过滤；分层对齐。
  - 模块 1 任务 2–7：yfinance 价格、Qlib dump、Alpha158 基线。
- 遗留问题：
  - 单一股票规则剔除 62% 的 S&P 行，样本只有 50 万条；若后面样本不够，可讨论"保留 ≤2 个 ticker 的文章并分别归属"。
  - 有时刻子集只有 2,511 行，按精度分子样本的分析在 FNSPID 上基本做不了；16:00 ET 口径与主口径几乎相同。
  - FNSPID 按 ticker 的时间覆盖不均匀，股票-日面板会稀疏且非随机缺失；是以后考虑 Alpaca 等补充来源的理由。
  - 70 只成分股没有任何候选新闻；`BRK` 未映射。
  - 模型加载从网络卷冷启动 37 秒（热 7.5 秒）。
  - 这台宿主机的 L40S 持续热降频，吞吐只有试跑峰值的 65%；下次开 Pod 若仍如此，可换机房或 RTX 6000 Ada。plan.md 5.5 节的耗时估算应按约 6.5k tok/s 修正（原文每 100 万篇约 20 小时）。
  - 分片写盘约 9 秒/片（zstd 压 float16 几乎无效），以后新模型可改 compression=none。

## 2026-10-22 · 模块 0 完成

- 做了什么：bootstrap 跑通，两个 venv（`venv-main`、`venv-vllm`）建好；LLaMA3-8B 权重校验通过；
  smoke-embed 吞吐 11,144 tokens/s（约合每 100 万篇 11.2 小时）；smoke-vllm 通过；`make lock` 锁定版本；
  Claude Desktop SSH 会话已连通，环境识别正确（pod，`NCPU=17`，L40S）。
- 产出在哪：`/workspace/venv-main`、`/workspace/venv-vllm`、`/workspace/hf_cache`；lock 文件已提交到仓库。
- 下一步：模块 1（新闻解析与对齐）。
- 遗留：
  - vLLM 摘要 10 条中有 3 条加了原文没有的内容，其中 1 条与原文矛盾；模块 3 放量前先改提示词并做对比。
  - venv-main 冷启动 import 耗时 21 秒，待复测。

## 2026-10-21 · 模块 0：环境

- 做了什么：RunPod 账户、SSH 密钥、网络卷 `llm-news-vol`（US-IL-1，250 GB）、模板 `llm-news-l40s`、首个 L40S Pod；
  `env.sh`（线程数按 cgroup 配额）、`bootstrap.sh`、Claude Code 配置持久化；HF 与 GitHub token；
  LLaMA3-8B base 与 Instruct 权重下载到 `/workspace/hf_cache`（共约 30 GB，已排除 `original/`）；仓库骨架。
- 实测：L40S 显存 46068 MiB；cgroup v1 CPU 配额 17.85 核（`NCPU=17`）；内存上限约 125 GB；
  SSH 会话读不到模板环境变量（由 `env.sh` 注入解决）。
- 下一步：首次完整 bootstrap（两个 venv + Qlib）→ `make check-env` → `make verify-llama` → `make smoke` →
  `make lock` → 连接 Claude Desktop SSH 会话。
- 遗留：网络卷上的 venv import 耗时待测；若过慢，改为打包后解压到容器盘。
