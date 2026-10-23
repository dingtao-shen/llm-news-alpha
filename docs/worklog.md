# Worklog

新条目写在最上面。每条：做了什么 / 产出在哪 / 下一步 / 遗留问题。

## 2026-10-23（续 6）· Phase A 收口（进行中）：日期校验、市值、DM 检验、信号拆分、λ 口径

- 做了什么：
  - 日期/时区校验（模块 2 任务 4）：benzinga.com 与 nasdaq.com 对数据中心 IP 返回 Cloudflare 403，改用 Wayback 快照（`news/validate_timezone.py`，400 条样本，
    单线程 + 2.5 秒间隔 + 429 退避，运行超过 1.5 小时，结果待写）。不依赖抓取的全量检查：nasdaq.com 2015–2021 有 900,006 行 URL 末尾带日期，
    与 FNSPID 日期相同 99.1%，0.9%（仅 2019–2021）URL 日期晚一天；Benzinga URL 年月与 FNSPID 一致 99.99%，5% 的仅日期行 FNSPID 日期晚于 URL 月份（滞后，安全）。
  - 市值（模块 1 任务 6，`data/market_cap.py`）：SEC companyfacts 股数 × 调整后收盘价。三个坑都处理了：companyfacts 不含维度事实，多类别公司（GOOGL、FOX、BRK）
    的 dei 股数缺失或零碎 → 回退到合并口径 us-gaap 元素；披露股数已反映申报日前的拆股，拆股换算按 filed 而不是 end（否则 GOOG 2022 多算 20 倍）；
    量级错误（PKG 按千股填报）在换算后按 8 倍阈值剔除；伯克希尔按 A 类等价股披露，B 股乘 1500。631 只中 553 只有股数，90% 股票-日有市值，其余 adv20 代理。
    抽查 2019/2023 年末前六名与真实市值一致。SEC 现用代码表没有 2024 年后退市/改名的公司（MMC→MRSH、BK→BNY 已加别名）。
  - DM 型检验（`analysis/dm_test.py`，日度 Rank IC 配对差，NW 滞后 5）：只有 ChronoBERT 原文显著异于 0（t 2.13）；28 对里只有 2 对显著（ChronoBERT 原文 > ChronoBERT 标题、> FinBERT 原文）。
  - 信号拆分（`analysis/signal_decomposition.py`）：主口径分数对隔夜收益（t 收盘→t+1 开盘）的 Rank IC：ChronoBERT 原文 +0.0166（t 3.4）、LLaMA3 原文 +0.0215（t 3.9），
    对 t+1 日内收益 ≈ 0，对主标签 +0.009 / +0.0065。**信号在隔夜兑现，次日开盘后几乎不剩。** 2020–2023 测试样本几乎全是 nasdaq.com 全文，来源拆分对原文模型无信息；
    单条新闻的股票-日携带 ChronoBERT 的信号（+0.0115，t 2.44）。
  - λ 口径（`--lambda-rel`，`results/ridge/lambda_sensitivity.md`）：固定 λ_rel=10 在 8 个组合里 6 个全期 Rank IC 更高（LLaMA3 标题 0.0010→0.0054），验证年选 λ 是噪声。
    注意事后选固定值本身有轻微前视，正式口径应预先固定或用多年验证平均。
- 产出在哪：`/workspace/data/market_cap/market_cap.parquet`、`/workspace/data/raw/sec/`；`results/prices/market_cap_coverage.{md,csv}`；
  `results/ridge/{dm_test,signal_decomposition,lambda_sensitivity}.md`、`*__lam10.*`；`results/news/tz_check.*`（待 400 条结果）。
- 下一步：Wayback 结果出来后定日期规则（候选：nasdaq.com 取 max(FNSPID 日期, URL 日期)）；评估"16:00 截止 + 收盘成交"口径能否吃到隔夜收益
  （取决于 nasdaq.com 文章发布时刻分布）；Alpaca 需要用户注册拿 API key；BRK.B 增量嵌入；Phase B（摘要、词袋基线、PCA）。
- 遗留问题：Wayback 校验脚本原来只在结束时输出，无法看进度（已改为每 10 条打印一次）；SEC 没有 160 只退市公司的 CIK，市值缺口 10% 用 adv20 代理。

## 2026-10-23（续 5）· 模块 6 任务 1–2：五分位多空（等权）、成本、EWCT

- 做了什么：`analysis/longshort.py`（`make longshort`，8 秒）：每日按 score 在有新闻的股票里做多前 20%、做空后 20%，等权美元中性，
  t+1 开盘建仓、t+2 开盘换仓（用标签 ret_oo），不足 10 只空仓；成本 = 费率 × Σ|Δw|（0/5/10/20 bps）；EWCT w_t = ω w*_t + (1−ω) w_{t−1}，ω ∈ {1, 0.9, 0.7, 0.5, 0.3, 0.2, 0.1}。
  对 preds 里 8 个 模型×文本 跑完，ChronoBERT 四个版本拼成一条序列。结果 `results/longshort/sharpe_table.{md,json}`、每日毛收益 CSV、累计收益图。
- 结果：ω=1 的毛夏普 0.26–0.90（ChronoBERT 原文 +0.90、MiniLM 标题 +0.56、LLaMA3 原文 +0.53、LLaMA3 标题 +0.46、FinBERT 原文 −0.25），
  年化收益 −3.5% 至 +13.3%，波动 12–16%。日均换手 Σ|Δw| ≈ 3.5（接近每日完全换仓的上限 4），10 bps 下每天成本约 35 bps，
  **扣费后夏普全部为 −5 至 −7**；EWCT 到 ω=0.1 把换手压到 0.3，但毛夏普随之降到 0.2–0.4，净夏普仍为 −0.6 至 −1.5。5 bps 也全负。
  分年：2022 年几乎全部为负，2021 年 LLaMA3 原文 +3.19 为单年最高。
- 对照原文：原文等权多空夏普 4.59（全市场），EWCT 0.1 扣费后 0.77；本项目大盘股 + 免费数据下毛夏普不到 1、扣费后为负，
  与"大盘股信息效率高、新闻在次日开盘前已基本吸收"一致，是报告里的核心负结果。
- 产出在哪：`results/longshort/`。
- 下一步：市值加权（等历史市值）；十分组稳健性；按来源 / 新闻条数 / 当天收益分位拆分；DM 检验；16:00 口径；多头 Qlib TopkDropout 补充；
  探索更低换手的持仓方式（如只在新闻日交易、持有 k 天）作为报告的"成本可行性"讨论。
- 遗留问题：等权组合里每天只有有新闻的 20–60 只股票进入多空，分散度低、波动大；没有市值权重；无 DM 检验前模型间差异不能下结论。

## 2026-10-23（续 4）· 表 A 初表：4 个模型 × 标题/原文

- 做了什么：`models/run_table_a.sh`（`make table-a`）顺序跑完 LLaMA3 原文、FinBERT、MiniLM 的标题与原文、ChronoBERT 四个版本各自窗口的标题与原文
  （`--test-years` 单测试年），`analysis/table_a.py` 汇成 `results/ridge/table_a.md`。全链 8 分钟（聚合 + Ridge；LLaMA3 原文聚合约 2 分钟）。
- 结果（全期日均 Rank IC，2020–2023，按交易日加权）：
  LLaMA3 标题 +0.0010 / 原文 +0.0065；ChronoBERT 标题 −0.0012 / 原文 **+0.0090**（ICIR 0.068，四年中三年为正）；FinBERT 标题 +0.0037 / 原文 −0.0004；MiniLM 标题 +0.0009 / 原文 +0.0031。
  规律：原文普遍优于标题（FinBERT 例外）；2022 年所有组合都为负；LLaMA3 原文 2021 年 +0.0295 是单年最高；所有数字都在 0.01 量级，
  模型之间的差异在噪声范围内（原文表 4 的结论在这里更明显），下结论要靠 DM 检验。时间一致的 ChronoBERT 原文不输 LLaMA3 原文，
  初步支持"LLaMA3 的前视偏差影响有限"这一差异化点，但统计功效很低。
- 产出在哪：`/workspace/data/agg/<model>/<text>/main/`、`/workspace/data/preds/<model>__<text>__main.parquet`（接口文件 3，8 个文件 + ChronoBERT 4 个版本各 1 个）、
  `results/ridge/*.{md,json}`、`results/ridge/table_a.md`。
- 下一步：模块 6 的五分位多空回测（等权 / 市值加权、成本、EWCT）把 Rank IC 转成夏普；DM 检验；按来源 / 新闻条数 / 当天收益分位拆分信号去向；
  16:00 口径；AI 摘要（模块 3 任务 4）；弱文本基线（LM 词典、TF-IDF）。
- 遗留问题：ChronoBERT 各版本用 ts_utc 年份过滤窗口，与 feature_day 年份在年末相差几十行（n_test 92,777 vs 92,825），无实质影响；
  验证年选出的 λ 在网格两端乱跳，验证 IC 曲线平坦，λ 选择本身接近随机，可考虑固定 λ 或按多年验证平均。

## 2026-10-23（续 3）· 模块 3 任务 5–6：聚合、滚动 Ridge、第一张文本 IC 表（LLaMA3 标题）

- 做了什么：
  - `models/labels.py`：Qlib 一次算出 6 个口径标签（主标签开盘到开盘、收盘到收盘、建仓推迟 1–4 天），成分股区间内 1,063,968 个股票-日 → `/workspace/data/labels/labels_sp500.parquet`。
  - `models/aggregate.py`：news_clean × 嵌入分片 → (feature_day, ticker) 均值嵌入 + news_cnt/n_timed/n_body/in_sp500，按年 parquet（`/workspace/data/agg/llama3_base/title/main/`，196 秒）。
    每年约 2.4 万–3.4 万个 in_sp500 股票-日，平均 1.7 篇新闻/股票-日。
  - `models/ridge_suffstats.py`：按年 float64 充分统计量，一次特征分解解整条 λ 路径（15 个相对 trace(S)/P 的 λ），4+1+1 滚动，验证年按日均 Rank IC 选 λ，
    6 个标签同时求解；输出接口文件 3 `/workspace/data/preds/llama3_base__title__main.parquet`（92,825 行，score + score_<label>）与 `results/ridge/`。全程约 2 分钟。
  - **结果（LLaMA3-8B 标题，主口径）**：测试年 Rank IC 2020 +0.0044、2021 +0.0027、2022 −0.0115、2023 +0.0086；全测试期日均 Rank IC +0.0010，ICIR 0.008。
    其他标签：收盘到收盘与推迟建仓的 Rank IC 也都在 ±0.02 内、符号不稳定。
  - 链路诊断 `analysis/sanity_contemporaneous.py`：同一嵌入预测新闻当天收益 ret_t0 的样本外 Rank IC 为 +0.10 至 +0.19（ICIR 0.8–1.5，四年全正），
    说明嵌入含有很强的情绪信息且对齐正确；t 收盘到 t+1 收盘 +0.003 至 +0.019（四年全正）> 开盘到开盘。
    结论：**不是 bug，是信号在到达可交易的次日开盘前已基本被吸收**，与原文"大盘股新闻效应 1–2 天内吸收、市值高于中位数子样本 IC 低"一致，且比预期的 0.5–1% 更低。
- 产出在哪：`/workspace/data/{labels,agg,preds}/`；`results/ridge/llama3_base__title__main.{md,json}`、`results/ridge/sanity_contemporaneous_llama3_base__title__main.md`。
- 下一步：
  - 同一流水线跑原文（body）与其他模型（FinBERT、MiniLM、ChronoBERT 滚动）填满表 A 的标题/原文列；再做 16:00 口径。
  - 分析信号去向：按来源（Benzinga 标题 vs nasdaq.com 全文）、按新闻条数、按 ret_t0 的分位拆分 IC；考虑把"隔夜反应"作为报告中的核心发现之一。
  - 模块 6 的五分位多空回测与成本；模块 5 的表 B。
- 遗留问题：主标签 IC 接近 0，后续比较（文本类型、模型、时间一致性）可能都落在噪声范围内，报告要以 DM 检验和置信区间说话；
  λ 在验证年选出的值在 0.001–1e4 之间大幅跳动，说明验证 IC 曲线很平（信号弱）。

## 2026-10-23（续 2）· Alpha158 + LightGBM 基线（模块 1 任务 7）

- 做了什么：`qlib_ext/handler.py` 加 `Alpha158NoVwap`（去掉 VWAP0，我们没有 vwap 数据；默认标签改为开盘到开盘）；
  `configs/baseline_alpha158.yaml`（训练 2015–2018、验证 2019、测试 2020–2023；TopkDropout 50/5、deal_price open、单边 5 bps、基准 SPY）；
  `make qlib-baseline` 用 qrun 跑通（数据加载 47 秒，全程约 2 分钟），MLflow 实验 `baseline_alpha158_lgb`，recorder 085a90c7…；
  `analysis/baseline_report.py` 从 recorder 取 IC 与回测指标，写 `results/baseline/`。
- 结果：IC 0.0066、ICIR 0.055、Rank IC 0.0058；Top-50 多头超额收益扣费前 +0.4%/年、扣费后 −0.6%/年，信息比率 ≈ 0；LightGBM 第 5 轮早停。
  链路检验（`results/baseline/baseline_sanity_checks.md`）：特征 NaN 0.003%、训练 45.6 万行；昨日收益反转因子 Rank IC −0.018（ICIR −0.08），
  说明数据没问题、是模型在当前超参下几乎没学到东西。
- 产出在哪：`/workspace/mlruns/`（实验、pred.pkl、port_analysis、report_normal）；`results/baseline/baseline_alpha158_lgb.{md,json}`、`_cum_return.png`、`baseline_sanity_checks.md`。
- 下一步：模块 3 任务 5–6（股票-日聚合、充分统计量 Ridge）→ 第一张文本 IC 表；模块 5 再用 Optuna 以验证年 Rank IC 重调 LightGBM，并加入"昨日收益反转"单因子基线。
- 遗留问题：基线本身很弱，作为对照组时要同时报告反转单因子；回测日志有 "$open field data contains nan"（个别缺价格日），
  Qlib 提示没有 future calendar（仅警告）。

## 2026-10-23（续）· 价格缺口补齐、Qlib dump

- 做了什么：
  - `data/fill_prices_fnspid.py`：用 FNSPID `Stock_price/full_history.zip`（7,693 个文件）补 yfinance 缺失的价格。zip 有两个坑并已防护：
    （1）很多文件是两次抓取拼接的，旧段止于 2020-07-02 / 2020-04-01 且没有按之后的拆股调整（AAPL 在拼接处有 4 倍断点）；
    （2）同一文件可能拼接了先后使用同一代码的不同公司（FI = Frank's International → Fiserv，46 倍断点；CTRA = Contura → Coterra；PLL 是 Piedmont Lithium，ALTR 是 Altair）。
    对策：只取成分股窗口（前推 120 天、后推 10 天）内的行；拼接处断点 > 40% 则丢弃前段；末行离群值丢弃；乒乓错行置 NaN；不用别名。
    结果 79 只补入，85 只两边都没有；价格覆盖 631/716 只、592/723 个区间。
  - `make qlib-dump`：632 个 CSV → `/workspace/qlib_data/us_sp500`（9 秒）。校验见 `results/prices/qlib_dump_check.md`：日历与 SPY 完全一致，
    成分股区间内股票-日有价格 93.2%（2015 年 85.2% → 2023 年 98.3%），标签表达式可算，28 条 |收益| > 50% 均为真实事件。
  - 价格元数据移到 `/workspace/data/prices/_meta/`（dump_bin 会把同级 *.csv 都当成股票）。
- 产出在哪：`/workspace/data/prices/*.csv`（+ `_meta/{manifest,failed,sources,fnspid_fill}.json|csv`）、`/workspace/qlib_data/us_sp500/{calendars,features,instruments}`、
  `results/prices/{price_coverage.md,price_coverage.csv,qlib_dump_check.md}`。
- 下一步：模块 1 任务 7 Alpha158 + LightGBM 基线（`configs/baseline_alpha158.yaml`，`qrun`）；模块 1 任务 6 市值；模块 3 任务 5–6 聚合与 Ridge。
- 遗留问题：85 只早年退市公司没有价格（2015–2017 股票池偏向幸存者，报告中要写明）；WBD 两边都没有；KSU 等 FNSPID 旧抓取只到 2020-07 的区间后半段缺失。

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
  - `/workspace/data/news/news_clean.parquet`（476,895 条，接口文件 1）、`news_panel.parquet`（272,885 个股票-日）、`news_clean_meta.json`：
    用户确认后已用修正版替换第一版；`results/news/news_clean_report.md` 为对应数字
  - `infra/make_dev_sample.py` → `/workspace/data/dev_sample.tgz`（70 MB，Mac 的 dev_data/）
- 下一步：
  - 候选集重建时带 BRK 别名并做增量嵌入（embed.py 需要支持追加分片）。
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
