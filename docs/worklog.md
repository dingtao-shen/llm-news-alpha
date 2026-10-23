# Worklog

新条目写在最上面。每条：做了什么 / 产出在哪 / 下一步 / 遗留问题。

## 2026-10-23 · 小模型嵌入、价格下载、模块 2 任务 5–8（Pod 上继续开发）

- 做了什么：
  - `text/embed.py` 泛化：`--model finbert|minilm`、`--model chronobert --version YYYYMMDD --years Y0 Y1`（按年滚动窗口）、FinBERT 的 BertModel/BertTokenizerFast 回退。
    `make embed-small` 一条链跑完：FinBERT、MiniLM 全集，ChronoBERT 四个版本（(Y-1)1231，窗口 [Y-5, Y]，Y=2020–2023）。合计约 50 分钟。
    吞吐：FinBERT 356k/399k tok/s，MiniLM 695k/2.16M，ChronoBERT 约 150k/135k（标题/原文）。所有 14 套嵌入分片数、行数与 _meta.json 一致，float16 无 NaN。
  - `data/download_prices.py`：yfinance 分批下载 716 只 + SPY → `/workspace/data/prices/<ticker>.csv`（date, symbol, OHLCV, adj_close, factor=adj_close/close）。
    552 只成功、164 失败（逐只重试确认 Yahoo 已不提供：多为 2024 年后被收购/私有化/改名）；成分股区间 549/723 有完整价格。
    **缺口集中在 2015–2022 年退出指数的公司**（2015 年退出的 27 个区间只有 6 个有价格），对无幸存者偏差回测是实质问题。
    `data/ticker_aliases.yaml` 收录 6 个改名（FB→META 等）。Yahoo 的 Close 已按拆股调整，factor 只含分红（与 Qlib 官方 collector 口径一致）。
  - 模块 2 任务 5–8：`news/ticker_map.py`（BRK→BRK.B 别名）、`news/align.py`（向量化分层对齐，9:00 主口径 t = prev(d)，16:00 口径 t = d，day 精度 23:59:59）、
    `news/filters.py`（正文 100–100,000 字符；同股票 5 个交易日内词袋余弦 ≥ 0.8，去停用词 + 对数词频）、`news/build_clean.py`（→ news_clean.parquet、news_panel.parquet、报告）。
    测试抓到 bug：day 精度的 `00:00:00 UTC` 是日历占位，不能按 UTC 瞬时转美东（会把特征日提前一天）。
    近似重复第一版用原始词频剔了 16%，抽查一半是误杀（长正文被停用词主导）；改为去停用词 + log(tf) 后剔 5.6%，剩下的都是电讯更新版与模板文章。
  - 全量结果（修正版）：476,895 条，有时刻 2,417，in_sp500 414,770；股票-日覆盖率 20.6%（2021 年 13.5% 最低，2019 年 27.0% 最高）；日历暂用 SPY 交易日。
- 产出在哪：
  - `/workspace/data/emb/{finbert,minilm,chronobert-2019123,…}/{title,body}/part-*.parquet`；`_inputs/` 下按窗口的输入表
  - `/workspace/data/prices/*.csv`、`_manifest.json`、`_failed.csv`；`results/prices/price_coverage.{md,csv}`
  - 修正版 news_clean / news_panel 暂在 Pod 容器盘 scratch（`/tmp/claude-0/.../scratchpad/clean_v2/`），`/workspace/data/news/` 下仍是第一版，等用户同意后替换；
    `results/news/news_clean_report.md` 已是修正版数字
  - `infra/make_dev_sample.py` → `/workspace/data/dev_sample.tgz`（70 MB，Mac 的 dev_data/）
- 下一步：
  - 替换 news_clean 为修正版（待确认）；候选集重建时带 BRK 别名并做增量嵌入（embed.py 需要支持追加分片）。
  - 价格缺口：用 FNSPID `Stock_price/full_history.zip`（2023 年抓取，含当时的退市股）补 164 只；再 Qlib dump、Alpha158 基线（模块 1 任务 3–7）。
  - 模块 2 任务 4：时区/日期校验（重点是仅日期记录的日期可靠性）；任务 9 其余统计。模块 3 任务 5–6：股票-日聚合、充分统计量 Ridge。
- 遗留问题：
  - 价格缺 164 只、集中在退市公司；嵌入缺 BRK.B 的新闻；日历暂用 SPY，最终换 Qlib `D.calendar()`。
  - 有时刻记录只有 2,417 行，16:00 口径与主口径只差 2,328 行，精度分组分析基本不可行。
  - GPU 热降频贯穿整晚（LLaMA3 原文 5.7k tok/s），小模型不受影响。

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
  - 正式嵌入已用 run_bg 启动（`make embed`，job `embed-llama3_base`，日志 `/workspace/logs/embed-llama3_base_20261022_161651.log`）：先标题全集（11 片，约 18 分钟），再原文子集（6 片，约 3.5 小时）。首片 5 万条实测 9,933 tok/s、padding 比 1.03、峰值 23.5 GB；之后 GPU 热降频（88–89 °C，SM 840–1170 MHz，throttle reason SW thermal slowdown），稳定在约 6.2–6.5k tok/s。标题全集 16:41 UTC 完成：11 片、8,853,188 token、6,543 tok/s、24 分钟。原文子集 22:44 UTC 完成：6 片、270,049 条、124,342,956 token、5,741 tok/s（逐片从 6.2k 降到 5.5k）、6.0 小时。两种文本的嵌入均已落盘并校验。
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
