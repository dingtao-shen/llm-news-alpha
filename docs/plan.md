# 《Expected Returns and Large Language Models》Qlib 复现计划

2026-10-22 · @DT S

## 1. 项目定位与目标

本项目在 Qlib 中复现 Chen、Kelly、Xiu《Expected Returns and Large Language Models》的核心框架：用 LLM 把个股新闻转为向量表示，再用监督模型预测次日截面收益并构建多空组合。市场选美股 S&P 500，新闻数据用免费的 FNSPID 替代原文的 Refinitiv 新闻库。全部计算（新闻清洗、嵌入、摘要、全维 Ridge、Qlib 建模、回测与分析）在 RunPod 云端一台固定配置的机器上完成；本地只有一台 MacBook Air，不装 torch 和 Qlib。代码开发全程由 Claude Code 辅助，在两处进行：Mac 本地会话负责纯逻辑、单元测试、文档与规划，Pod 上的 SSH 会话负责需要真实数据、GPU 或 Qlib 才能验证的代码；两边通过 GitHub 仓库同步。

**学习目标**

- 走通 Qlib 的完整链路：自建数据 → 自定义特征与 Handler → Dataset → Model → 回测 Strategy → SigAnaRecord / PortAnaRecord 分析。
- 掌握另类数据因子研究的关键环节：文本时间戳与交易日对齐、前视偏差控制、高维嵌入的收缩回归与降维、与量价因子的增量检验。
- 理解论文的研究设计逻辑：为什么用嵌入而不是 prompt 打分、为什么比较不同类别的文本表示、为什么关心 LLM 的前视偏差、为什么按市值和新闻新鲜度分组。
- 掌握云端一体化研究环境的工程做法：固定配置、持久化存储卷、长任务后台化、吞吐实测与成本控制、AI 辅助的远程开发。

**简历目标**

- 产出一个可公开的 GitHub 仓库和一份 3–5 页研究报告，有基线、有提升幅度、有成本假设、有至少一个消融结论。
- 面试时能从经济逻辑、数据处理、模型选择、回测稳健性四个角度讲清楚整个项目。

**范围边界**

| 做 | 不做 |
| --- | --- |
| 美股 S&P 500 时点成分股，2015–2023 日频，样本外测试期 2020–2023 | 盘中/高频交易 |
| 新闻数据只用 FNSPID；Alpaca 等其他新闻源列为可扩展选项 | 第一轮同时接入多个新闻源 |
| 三种文本输入：标题；原文（标题 + 正文前 512 token）；LLaMA3-8B-Instruct 生成的 AI 摘要 | 超过 512 token 的长文本（原文附录表 IA10 显示加长输入几乎没有增益）、财报电话会议文本 |
| LLaMA3-8B 与按年滚动的 ChronoBERT 嵌入；FinBERT、MiniLM 为对照 | 调用付费大模型逐条 prompt 打分；LLaMA2-13B 等规模对照 |
| 全维 Ridge（贴近原文）+ MLP、随机森林、LightGBM | 从零实现新的深度网络结构 |
| 与 Qlib Alpha158 基线对比与融合 | 16 个国际市场的全面复现（港股只作最低优先级可选扩展） |
| 规模分组、新闻动量衰减、成本与换手控制、文本形式对比、时间一致模型对照、时间戳精度分组 | 月频预测版本 |
| 全部实验在云端同一台固定配置的机器上运行 | 本地训练或本地回测 |

## 2. 论文核心工作与模型设计分析

论文把"个股新闻文本 → 次日收益预测"做成一条标准化的两步流水线。第一步用冻结参数的 LLM 把每篇新闻编码成向量；第二步把向量当作特征，用收缩回归（基准为 Ridge）预测收益，相当于在冻结的 LLM 上加一个线性"头"，不重新训练 LLM。在这条流水线上，论文系统比较了从词袋到 LLM 的各类文本表示。

核心结论是：LLM 嵌入显著优于词典法、主题情绪模型和 word2vec；价格对新闻的反应存在可利用的滞后。不同类别模型之间的层级很清楚，但顶层几个 LLM 之间的差异在统计上不显著（表 4），LLaMA 家族内部换参数规模，增益也不大、不单调（附录表 IA8）。论文仍是工作论文（作者主页列为 2026 年 2 月版），获 2023 GSU-RFS FinTech 会议最佳论文奖。

本节依据项目中的论文全文（SSRN 4416687 最新版）撰写，表号、图号均指该版本。

**2.1 研究问题与经济逻辑**

- 问题：新闻文本中是否含有尚未被价格反映的信息？用什么文本表示能最完整地提取它？
- 逻辑：新闻信息进入价格有延迟（limits-to-arbitrage），因此当日新闻可以预测次日收益，表现为短期"新闻动量"；延迟在小盘股上更明显，大盘股的新闻效应 1–2 天内基本被吸收。
- 方法论立场：用嵌入做"开放式"信号提取，而不是用 prompt 让模型直接判断。作者的比喻是"用网捕鱼"对"用竿钓鱼"：prompt 受研究者提问能力限制，嵌入保留文本的全部信息，再交给监督模型筛选。

**2.2 数据设定（原文）**

| 项目 | 原文设定 |
| --- | --- |
| 新闻来源 | Refinitiv 的 RTRS（路透）与 3PTY（第三方）新闻库。美股新闻分"文章"（标题 + 正文）与"快讯"（只有标题的突发新闻） |
| 样本期 | 1996-01 至 2019-06；美股文章另延长到 2022-05，只用于稳健性与前视偏差检验 |
| 样本量 | 过滤后美股文章 3,038,025 篇、快讯 2,935,852 条（表 2） |
| 过滤规则 | 只保留对应单一股票的新闻；长度在 100–100,000 字符之间（快讯不适用）；用词袋表示计算，与前 5 个交易日内另一篇文章余弦相似度 ≥ 0.8 的视为重复剔除 |
| 收益与市值 | 美股用 CRSP，国际市场用 Datastream |
| 时间对齐 | 预测开盘到开盘收益；截至当日 9:00 ET 的新闻在当日开盘建仓，持有到下一个开盘；9:00–9:30 ET 发布的新闻挪到下一天的输入 |
| 训练方式 | 每年滚动：8 年窗口（6 年训练 + 2 年验证），测试下一年；样本外 2004–2019，共 16 年 |
| 嵌入 | 最后一层隐状态做均值池化；基准取文章前 512 token |
| 组合 | 每日按预测收益做多前 20%、做空后 20%（五分位），等权与市值加权 |
| 交易成本 | 每 100% 换手：大盘股 10 bps、小盘股 20 bps（以 NYSE 市值 20% 分位为界）；配合 EWCT 换手控制 |
| 市场 | 美国在内 16 个市场，新闻涉及 13 种语言 |

**2.3 信号构建**

1. 文本表示 x_{i,t}：对每篇新闻生成一个 P 维向量。词袋类方法给出词频向量；LLM 取最后一层隐状态，对所有 token 做均值池化。
2. 收益回归：以次日开盘到开盘收益为因变量，对 x 做 Ridge 回归，得到预期收益 r̂_{i,t+1}，正则强度在验证集上选（网格很宽，见原文脚注 18）。预测值直接作为截面排序变量。为了可比，最新版所有模型统一用次日收益做标签（脚注 10）；早期版本用"新闻前后 3 日收益符号"训练情绪分类器，已不是主分析。
3. 非线性扩展：Lasso 明显更差；随机森林与神经网络更好（LLaMA3 嵌入下等权多空夏普分别为 5.51、5.26，Ridge 为 4.59，表 7）。作者认为信号很弱时稠密模型优于稀疏或选择性方法，因此没有使用提升树。

**2.4 比较的文本表示模型**

| 类别 | 模型 | 说明 |
| --- | --- | --- |
| 词典法 | LM 词典（Loughran-McDonald） | 人工构造的金融情绪词表 |
| 词袋 + 监督 | SESTM（Ke, Kelly, Xiu） | 从收益中学习词的情绪权重 |
| 静态词向量 | word2vec | 词级嵌入，无上下文 |
| 编码器 LLM | BERT-large（3.4 亿参数）、RoBERTa | 双向上下文嵌入 |
| 解码器 LLM | LLaMA、LLaMA2、LLaMA3（8B） | 生成式模型，取隐状态作嵌入 |
| API 嵌入 | "ChatGPT"，即 OpenAI text-embedding-3-large | 3072 维嵌入，与其他模型走同一条流水线；不是 prompt 打分。原因是 ChatGPT 本身拿不到嵌入（脚注 1） |

注：2022 年的早期版本主要使用 Meta 的 OPT 系列模型。

**2.5 组合构建与评价**

- 每日按预测收益做截面排序，做多前 20%、做空后 20%，等权与市值加权都报告，日频换仓。
- 预测评价：每日预测与次日实际收益的截面相关系数（即 IC）的时间序列均值，并单独报告市值高于 NYSE 中位数的子样本；模型之间用 Diebold-Mariano 检验比较预测精度。
- 分组分析：大小盘、新闻形式（快讯 / 文章 / 摘要）、含否定词的新闻、新闻主题、建仓延迟天数、短期反转双重排序。
- 模型集成：Kelly 的演讲幻灯片称所有 LLM 的集成优于单一最优模型；但原文图 7 显示各 LLM 组合的收益高度相关，集成带来的分散化可能有限。

**2.6 主要发现（最新版数字）**

- 收益与夏普：等权多空年化夏普 ChatGPT 4.78、LLaMA3 4.59；市值加权分别为 1.34、1.10（表 5）。
- 预测精度：日均 IC 全样本 ChatGPT 2.68%、LLaMA3 2.45%；市值高于 NYSE 中位数的股票中分别为 1.11%、1.19%（表 3）。
- 交易成本：LLaMA3 文章策略在 EWCT 参数 0.1 时扣费后夏普 0.77；快讯策略最高约 1.68（表 8）。换手越高，毛夏普越高、净夏普越低。
- 新闻动量：等权多空夏普在建仓第 1 天为 4.58，推迟一天降到 1.35（表 18）；大盘股的新闻效应 1–2 天内基本被吸收（图 10）；改用收盘价成交时，市值加权夏普从 1.10 降到 0.14（附录表 IA9）。
- 文本形式：LLM 生成的摘要比标题或全文更有效（LLaMA3 摘要等权夏普 5.42，表 16）；输入从 512 token 加长到 8K 几乎没有增益（附录表 IA10）。
- 否定与叙事：LLM 的优势在含否定词和复杂叙事的新闻中最明显，这是词袋法的典型盲区。
- 前视偏差：BERT、RoBERTa 在知识截止日之后的样本外表现没有下降（表 13）；实体匿名化后结论不变（表 15）；原文还引用了 He、Lv、Manela、Wu（2025）的时间一致模型结果，其组合表现与 LLaMA3 相当。
- 国际市场：结论在 16 个市场、13 种语言中稳健。

**2.7 对复现的启示**

- 保留主干：嵌入 → Ridge → 截面五分位排序 → 多空回测。Qlib 部分对应 Handler → Model → Strategy。
- 保留两类对照：一个弱文本基线（LM 词典、TF-IDF + Ridge）和一个量价基线（Alpha158），否则无法说明 LLM 嵌入的增量。
- 保留关键分析：大小盘、建仓延迟（新闻动量）、文本形式（标题 / 原文 / 摘要）、成本与换手、否定词子样本。
- 可简化：不做 16 个市场、不做月频、不做 LLaMA2-13B 等规模对照；ChatGPT 嵌入与模型集成列为可选扩展。

## 3. 原文设定与复现设定的对照

复现保留论文的方法主干，把付费数据和多市场替换成免费数据和单一市场；文本模型用原文主力模型之一 LLaMA3-8B，并加入时间一致的 ChronoBERT 作为前视偏差对照。每处替换都是一个可写进报告的差异化点。

| 维度 | 原文设定 | 本项目设定 | 理由 |
| --- | --- | --- | --- |
| 新闻数据 | Refinitiv（付费），过滤后美股文章约 304 万篇 | [FNSPID](https://huggingface.co/datasets/Zihan1004/FNSPID)：1999–2023 年、约 1,570 万条、4,775 只历史 S&P 500 标的；新闻原始文件 `nasdaq_exteral_data.csv` 23.2GB 与 `All_external.csv` 5.73GB | 免费、带时间戳与 ticker、以 S&P 500 公司为抓取范围 |
| 时间戳精度 | 全部精确到分钟 | 混合：一部分精确到秒，相当一部分只有日期（时间为 `00:00:00`） | 见 3.1；对齐规则相应分层 |
| 新闻过滤 | 单一股票、长度 100–100,000 字符、5 个交易日内余弦相似度 ≥ 0.8 视为重复 | 同左；近似重复按同一股票内比较；另按语言过滤掉俄语记录 | 对齐原文，减少重复新闻造成的伪信号 |
| 文本范围 | 文章前 512 token；另比较快讯与 AI 摘要 | 三种：标题（全集可用）；原文（标题 + 正文前 512 token，仅正文可用的子集）；LLaMA3-8B-Instruct 生成的摘要（同上） | 对应原文的文本形式比较；FNSPID 没有"快讯"，用标题近似 |
| 股票池 | 16 个市场中有新闻的股票 | 美股 S&P 500 时点成分股 | 数据可得；时点成分股控制幸存者偏差 |
| 样本期 | 1996–2019，样本外 2004–2019 | 2015–2023，样本外 2020–2023 | FNSPID 止于 2023；2015 年后新闻密度更高 |
| 文本表示 | BERT、RoBERTa、LLaMA 1/2/3、OpenAI 嵌入 | LLaMA3-8B（主力）；ChronoBERT 按年滚动版本（时间一致对照）；FinBERT、MiniLM（对照） | LLaMA3 是原文稳健性分析的主力模型；ChronoBERT 直接回应前视偏差质疑 |
| 嵌入维度 | 模型原始维度 | Ridge 用全维（LLaMA3 为 4096 维）；MLP 与随机森林用 PCA 256 维；Qlib 用 PCA 64 维；PCA 只在 2015–2018 年拟合一次 | 全维 Ridge 贴近原文；降维控制 Qlib 字段数量 |
| 训练方式 | 年度滚动：6 年训练 + 2 年验证，测下一年 | 年度滚动：4 年训练 + 1 年验证，测下一年 | 样本期较短，按比例缩短窗口 |
| 弱文本基线 | LM 词典、SESTM、word2vec | LM 词典情绪分 + TF-IDF + Ridge | 保留"LLM 相对词袋法的增量"这一核心对照 |
| 量价基线 | 过去收益等技术信号 | Qlib Alpha158 + LightGBM | Qlib 原生，便于做融合与增量检验 |
| 预测模型 | Ridge（基准）、Lasso、随机森林、神经网络 | 全维 Ridge（主）、MLP、随机森林、LightGBM | LightGBM 是偏离原文的选择（原文未用提升树），用于 Qlib 融合 |
| 标签 | 次日开盘到开盘收益 | 同左（主）；收盘到收盘为稳健性 | 与原文一致 |
| 新闻时间对齐 | 9:00 ET 截止，9:00–9:30 的新闻归下一天 | 分层：有时刻的记录用 9:00 ET 规则；仅有日期的记录视为当日 23:59 发布，次日开盘建仓。16:00 ET 截止为稳健性口径 | 仅日期记录只能保守处理，只会推迟信号、不会引入前视偏差 |
| 组合 | 五分位多空，等权与市值加权 | 同左（主）；十分组为稳健性；Qlib TopkDropout 多头为补充 | 与原文一致 |
| 交易成本 | 10/20 bps（按市值）+ EWCT | 10 bps（S&P 500 成分股都按大盘股）+ EWCT；另报告 0/5/10/20 bps 敏感性 | 与原文一致 |
| 算力 | 未披露 | RunPod L40S 48GB 一台，Secure Cloud 按需，全程固定配置 | 见第 5 节 |
| 市场 | 16 个市场 | 美股；港股作最低优先级可选扩展 | 集中精力于美股主线 |

**3.1 FNSPID 数据实况**

以下事实决定了模块 2 的设计，写进报告的数据部分：

- 构成：作者自己从 nasdaq.com 两阶段抓取（先抓标题与 URL，再按 URL 抓正文），再合并 Bloomberg、Reuters、Benzinga、Lenta 的既有公开数据。数据集是"nasdaq.com 全文 + 第三方历史数据拼接"的混合体。
- 字段：`Date, Article_title, Stock_symbol, Url, Publisher, Author, Article, Lsa_summary, Luhn_summary, Textrank_summary, Lexrank_summary`。每行是一个（新闻，股票）对，同一篇新闻可出现在多个 ticker 下。
- 时间戳精度混杂：数据卡预览里，2020 年 5 月之前的 Benzinga 记录几乎全部是 `00:00:00 UTC`，之后才出现具体时刻。nasdaq.com 抓取部分的精度待模块 2 统计。
- 正文缺失：Benzinga 来源的记录 `Article` 为空，只有标题和 URL。正文集中在 nasdaq.com 抓取部分，其中不少是 Zacks、Motley Fool 等转载的评论性文章，性质与原文的路透新闻有差异。
- 时区未经验证：数据卡标注 UTC，但部分记录的时刻在 UTC 和美东两种解读下都不合理，必须抽样校验。
- 文件质量：CSV 列类型不一致（数值列里出现俄语字符串，Hugging Face 数据查看器因此解析失败）；正文字段含换行与引号；含俄语 Lenta 记录。
- **news_id 定义（固定，不再改动；实现见 `news/news_id.py` 与 `news/parse_fnspid.py`）**：`norm_url` = 小写、去首尾空白的 URL，去掉开头的 `http://`/`https://` 与 `www.`，去掉第一个 `#` 或 `?` 及其后内容，去掉结尾 `/`；`norm_title` = 小写、去首尾空白、连续空白折叠为一个空格的标题；`news_id = sha256(norm_url + "\n" + norm_title)` 十六进制前 24 位。空 URL 或空标题按空串参与。同一篇新闻在多个 ticker 下得到同一 news_id。
- 许可：Hugging Face 数据卡标 CC BY-NC 4.0，GitHub README 写明可自由使用；本项目按研究用途使用，报告中两者都写明；仓库不重新分发原始新闻与摘要全文。

**3.2 解析后的实况修正（2026-10-22，模块 2 任务 1–2 实测，详见 `results/news/fnspid_parse_report.md`）**

- `All_external.csv` 是 `nasdaq_exteral_data.csv` 的真子集：共有的 11,551,494 个 news_id 两边 ticker、行数、日期、正文标记完全一致。流水线只用 nasdaq 文件；All_external 不再解析。
- 全部 28.6M 行中 9.8M 行没有 ticker（Reuters 856 万行有时刻但无 ticker，另有 Seeking Alpha、Lenta、Bloomberg 等）。带 ticker 的行 5.74M，其中**有时刻的只有 1.4%**（约 8.3 万行，集中在 2020 年 Benzinga）；nasdaq.com 全文 2015–2022 年时刻可用率为 0。影响：主口径实际上几乎全由"仅日期 → 当日 23:59 → 下一交易日开盘"规则覆盖；表 A 的"有时刻"一栏样本很薄，16:00 ET 稳健性口径与主口径几乎相同，新闻动量"第一天效应"只能在小子集上检验，结论会弱。模块 2 任务 4 的重心改为验证**仅日期记录的日期可靠性**：抽样核对 FNSPID 日期不早于页面真实发布日（晚于只推迟信号，早于才是前视偏差）。
- 正文全部来自 nasdaq.com（带 ticker 且有正文 2.49M 行）；Benzinga 记录只有标题且止于 2020-06。2021–2023 年只剩 nasdaq.com 全文，训练期（Benzinga 标题为主）与测试期后半段来源构成不同。影响：报告中增加"按来源拆分"维度，Benzinga 仅标题记录对应原文的"快讯"，nasdaq.com 全文对应"文章"。2023 年一篇文章平均挂 4.2 个 ticker（19,497 篇挂了 10 个以上，是榜单类文章），单一股票规则会剔掉其中大部分，按原文规则不改。

**预期信号强度**

S&P 500 成分股基本都在 NYSE 市值中位数之上，相当于原文"市值高于 NYSE 中位数"的子样本。这个子样本中，LLaMA3 的 IC 约 1.2%、BERT 约 0.6%，全样本则为 2.45%（表 3）。再考虑到 FNSPID 的覆盖不如 Refinitiv、部分记录只有日期，本项目的合理预期是：纯文本信号 IC 在 0.5%–1% 之间或更低，市值加权多空夏普明显低于原文。信号弱于原文本身符合"大盘股信息效率更高"这一结论，报告中不视为失败。

**本项目的三个差异化点**

1. 时间一致模型对照：原文已做知识截止日后的样本外检验、实体匿名化，并引用了 ChronoBERT 作者的结果。本项目在免费数据和大盘股上复验这一结论：用按年滚动的 ChronoBERT（测试第 Y 年只用知识截止 Y−1 年底的版本）对照知识截止 2023 年 3 月、覆盖测试期的 LLaMA3-8B。
2. 增量信息检验：文本因子与 Alpha158 的相关性、融合后 Rank IC 的提升幅度。原文主要比较文本模型之间的差异。
3. 免费数据下的可复现性：报告 FNSPID 覆盖率、时间戳精度分布、信号强度相对原文的差距及其来源；按"有时刻 / 仅日期"两个子集分别报告 IC，检验 AI 摘要在免费数据上是否仍是最优输入。

## 4. 模块化复现计划

计划分 9 个模块。模块 0 搭环境；模块 1 产出量价基线与股票池；模块 2–3 产出新闻表、嵌入、摘要与全维 Ridge 预测；模块 4–6 产出主结果与分析；模块 7 为扩展实验；模块 8 收尾。除代码开发与最终作图外，所有模块都在云端同一台机器上运行。模块 0 和模块 1 的产出是所有后续实验的对照组，最先做完并冻结。

**流水线总览**

```text
价格流：时点成分股 + yfinance → Qlib 二进制 + 交易日历 → Alpha158 + LightGBM 基线（冻结）

新闻流：FNSPID 原始 CSV → 来源统计、解析、语言过滤、时区校验
        → 单一股票 / 长度 / 近似重复三条过滤
        → 分层对齐（有时刻：9:00 ET 规则；仅日期：当日 23:59）→ news_clean.parquet
        → 三种文本 → LLaMA3-8B / ChronoBERT / FinBERT / MiniLM 嵌入（+ Instruct 生成摘要）
        → 股票-日聚合 → 全维 Ridge（年度滚动）→ 样本外预测 pred.parquet
        → PCA-256 / PCA-64

汇合：  Qlib Handler（Alpha158 + PCA-64 + news_cnt + has_news）→ Ridge / LightGBM / MLP
        → SigAnaRecord / PortAnaRecord → 五分位多空、成本、分组与稳健性分析
        → results/ 表格与图表（唯一回传本地的产物）
```

模块之间只有三个接口文件：`news_clean.parquet`（新闻表）、嵌入分片（以 news_id 为键）、`pred.parquet`（datetime × instrument × score）。接口固定后，换数据源、换模型、换口径都只改一个模块。

**模块 0：环境（Mac + RunPod）——已完成**

- 目标：云端固定配置可用、持久化环境建好；本地能写代码、跑样本测试；Claude Code 本地会话与 Pod 上的 SSH 会话都能用。
- 建成的环境（细节见仓库 `infra/runpod_template.md` 与 `infra/bootstrap.sh`）：
  1. RunPod：SSH 公钥已加入账户；网络卷 `llm-news-vol`（US-IL-1，250GB，Standard）；自定义模板 `llm-news-l40s`（官方 PyTorch 镜像，容器盘 100GB，网络卷挂载到 `/workspace`，暴露 TCP 22 与 HTTP 8888）。
  2. 密钥：`/workspace/.secrets/env`（权限 600）存 `HF_TOKEN`（Read 类型）、`GH_TOKEN`（只授权本仓库的 Fine-grained token，Contents 与 Pull requests 读写）、`GIT_NAME`、`GIT_EMAIL`。
  3. 模型：LLaMA3-8B base 与 Instruct 的使用许可已获批；权重已下载到 `/workspace/hf_cache`（共约 30GB，排除了 `original/` 目录），`make verify-llama` 校验 commit 与全部分片 SHA-256 通过。
  4. `env.sh`：插在 `~/.bashrc` 第一行，所有 shell（交互式、ssh 远程命令、Claude Code）都会加载；设置 `HF_HOME`、`PIP_CACHE_DIR`、`PYTHONPATH`、`MLFLOW_TRACKING_URI`、`VLLM_CACHE_ROOT`，按 cgroup CPU 配额设置 `NCPU` 与各类线程数，加载密钥，激活 `venv-main`（设 `VIRTUAL_ENV_DISABLE_PROMPT=1`，避免破坏 SFTP）。
  5. `bootstrap.sh`（幂等）：配置 git 身份与凭据（token 只从环境变量读取）→ 克隆或拉取仓库到 `/workspace/repo` → 安装 `env.sh` 与自身 → 安装 tmux、gh、rsync → 建 `venv-main`（`--system-site-packages`，复用镜像自带的 torch 2.8.0+cu128，并用 constraints 锁住）与 `venv-vllm`（独立环境，vLLM 0.32.0 + torch 2.13.0+cu130）→ 从源码 editable 安装 Qlib 0.9.8 → 打印汇总。requirements 变化时自动重装。
  6. 版本锁定：`requirements-main.lock` 与 `requirements-vllm.lock` 已提交。
  7. Claude Desktop 的 SSH 会话已连通 `/workspace/repo`，能正确识别环境与 `CLAUDE.md` 的约定。
- 验收实测：
  - L40S 显存 46068 MiB；驱动 595.91.07（最高支持 CUDA 13.2）；这台宿主机 cgroup CPU 配额 17.85 核（`NCPU=17`）、内存上限约 125GB。不同宿主机配额不同，代码按 94GB 内存预算。
  - `smoke-embed`：LLaMA3-8B 从卷上加载 8.3 秒、占显存 15.0GB；单条与批量嵌入余弦 0.99996（padding 屏蔽正确）；32 × 512 token 吞吐 11,144 tokens/s，约合每 100 万篇（450 token）11.2 小时；峰值显存 19.1GB。
  - `smoke-vllm`：需设 `VLLM_USE_FLASHINFER_SAMPLER=0`（本机没有 nvcc，FlashInfer 采样算子无法 JIT 编译）；KV cache 21 GiB、171,984 token；10 条摘要中 3 条加入了原文没有的内容，其中 1 条与原文矛盾（见模块 3 任务 4）。
  - import 耗时（冷启动）：venv-main 21 秒、venv-vllm 12 秒，待复测；若持续偏慢，再考虑把 venv 打包后每次解压到容器盘。

**模块 1：价格数据、股票池与市值（云端）**

- 目标：2015–2023 年 S&P 500 时点成分股的日频 OHLCV，转为 Qlib 二进制格式；准备近似历史市值；跑出并冻结 Alpha158 + LightGBM 基线。
- 现状约束：Qlib 官方美股数据止于 2020-11-10（[Issue #687](https://github.com/microsoft/qlib/issues/687)）；Yahoo collector 的美股股票列表接口已失效（[Issue #1953](https://github.com/microsoft/qlib/issues/1953)）；yfinance 批量下载会触发限流（[yfinance Issue #2422](https://github.com/ranaroussi/yfinance/issues/2422)）。因此价格数据必须自建。
- 任务：
  1. 股票池：从 [S&P 500 时点成分股数据](https://github.com/shardul0701/SP500-Survivorship-bias-data-2004-2026) 生成每只股票的进入/退出日期，写成 Qlib `instruments/sp500.txt`（格式 `ticker\tstart\tend`）。
  2. 下载：yfinance 分批（每批 20–50 只）、批间 sleep 1–2 秒、失败重试 3 次、落地 CSV 缓存到卷上。字段 date, open, high, low, close, volume，另加 `factor = adj_close / close` 作为复权因子。
  3. 转换：`python scripts/dump_bin.py dump_all --csv_path /workspace/data/prices --qlib_dir /workspace/qlib_data/us_sp500 --include_fields open,close,high,low,volume,factor`。
  4. 基准：下载 SPY 并一同 dump。
  5. 质检：统计可下载比例（退市股票往往缺失）、单日收益绝对值大于 50% 的记录、成交量为 0 的天数。
  6. 历史市值：首选 SEC EDGAR companyfacts 接口提供的历史流通股数，乘以收盘价得到近似市值；覆盖率不足时，用 20 日平均成交额作规模代理，并在报告中注明。
  7. 基线：复制 `examples/benchmarks/LightGBM/workflow_config_lightgbm_Alpha158.yaml` 为 `configs/baseline_alpha158.yaml`，修改 `provider_uri`、`region: us`、`market: sp500`、`benchmark: SPY` 与时间段，`qrun` 跑通并记录基线 IC 与回测曲线。
- 验收：覆盖率报告（成分股总数、成功下载数、按年份分布）；市值覆盖率；MLflow 中有基线的 SigAnaRecord 与 PortAnaRecord 输出。

**模块 2：新闻处理与时间对齐（Mac 样本开发，云端全量）**

- 目标：得到无前视偏差的新闻表（以 news_id 为键，带时间戳精度标记），以及 (trade_date, ticker) 粒度的新闻面板。
- 开发方式：用 `curl -L <文件地址> | head -n 300000 > dev_data/sample.csv` 流式截取前几十万行作为开发样本（截断处可能落在某篇正文中间，丢弃最后一条即可），解析、过滤、对齐的纯逻辑与 pytest 在 Mac 上写。原始文件直接下载到卷上，涉及全量数据的统计、时区校验与性能调试在 Pod 会话里做。
- 任务：
  1. 读取：全部列按字符串读取（DuckDB `read_csv(..., all_varchar=true)` 或 polars `infer_schema=False`），再逐列转换；必须用正规 CSV 解析器处理正文中的换行与引号。按规范化 URL + 规范化标题的 sha256 前 24 位生成 news_id（定义见 3.1 节，固定不改）。
  2. 来源与精度统计：按 Publisher / URL 域名统计条数、时刻可用率（时间是否为 `00:00:00`）、正文可用率、每年条数。这张表决定后面所有口径，放在最前面做。
  3. 语言过滤：剔除俄语（Lenta）记录；只保留 2015 年以后、标题非空的记录。
  4. 时区校验：从有时刻的记录中随机抽 100 条带 URL 的 Benzinga / nasdaq 记录，抓原文页面上的发布时间与 FNSPID 时间戳比较，确定偏移（0 小时为 UTC，4–5 小时为美东）；若样本内不一致，则这一来源的时刻全部作废，按仅日期处理。再从仅日期的记录中抽 100 条，确认页面日期不晚于 FNSPID 日期。校验结果写进 README。
  5. Ticker 映射：处理代码变更（如 FB→META）与已退市股票；无法映射的记录单独统计。
  6. 过滤（对齐原文）：
     - 单一股票：同一 news_id 出现在多个 ticker 下的，整篇剔除（Benzinga 的"今日异动股票"类列表会被这条规则自然剔除）；
     - 长度：正文长度不在 100–100,000 字符之间的剔除（只有标题的记录不适用）；
     - 近似重复：用词袋表示，与同一股票前 5 个交易日内文章的余弦相似度 ≥ 0.8 的剔除。
  7. 分层对齐（主口径）：统一成一个函数。对美东时间戳 τ，找到第一个满足"τ 早于当日 9:00"的交易日 d，这条新闻归入 d 的前一个交易日 t 的特征；标签是 t+1 开盘买入、t+2 开盘卖出，即在 d 开盘建仓。有时刻的记录直接代入 τ；仅有日期 c 的记录令 τ = c 当日 23:59:59 ET 再代入，效果是在 c 之后的第一个交易日开盘建仓。周末与节假日由同一条规则自动处理，交易日历用 Qlib 的 `D.calendar()`。每条记录保留 `time_precision ∈ {second, day}`。
  8. 稳健性口径：同时产出 16:00 ET 截止版本（有时刻且 16:00 前的归当日，其余归下一交易日；仅日期记录与主口径相同）。
  9. 统计：每年新闻条数、每只股票的新闻天数、有新闻的股票-日占比（按规模分组、按精度分组）、各过滤步骤剔除的条数。
- 验收：`news_clean.parquet`（news_id、ticker、美东时间戳、time_precision、标题、正文、两种口径的特征日）；来源与精度统计表；时区校验记录；随机抽 50 条人工核对日期归属。

**模块 3：嵌入、摘要与全维 Ridge（云端 GPU）**

- 目标：在云端产出全部嵌入、AI 摘要、全维 Ridge 的样本外预测，以及降维特征和统计量；产物全部留在卷上。
- 任务：
  1. 吞吐实测：先用 1,000–5,000 篇真实新闻实测各模型的每秒 token 数，并调大 batch（模块 0 的 smoke 测试只用了 19GB 显存），按实测值修正第 5 节的耗时与预算后再放量。模块 0 的初测为 LLaMA3-8B 11,144 tokens/s（32 × 512 token）。
  2. 三种文本：标题（全集）；原文（标题 + 正文，按各模型的分词器截断到前 512 token；仅正文可用的子集）；摘要（任务 4 的产出；同上）。
  3. 嵌入模型。均取最后一层隐状态做均值池化，以 news_id 为键、float16 分片写入卷，支持断点续跑：
     - LLaMA3-8B base：4096 维，bf16 推理；
     - ChronoBERT 按年滚动：测试第 Y 年用知识截止到 Y−1 年底的版本（`manelalab/chrono-bert-v1-<Y−1>1231`），只对该滚动窗口的 6 年数据做嵌入；
     - FinBERT（`yiyanghkust/finbert-pretrain`）与 MiniLM（`all-MiniLM-L6-v2`）作对照。MiniLM 最长只能输入 256 token，报告中注明截断差异。
  4. AI 摘要：在 `venv-vllm` 里用 LLaMA3-8B-Instruct + vLLM 批量生成，固定解码参数（temperature = 0），脚本在 `import vllm` 之前设 `VLLM_USE_FLASHINFER_SAMPLER=0` 与 `OMP_NUM_THREADS=4`。
     - 放量前先改提示词：模块 0 的旧提示词在 10 条里有 3 条"加料"（补充后果、补充动机、写出与原文矛盾的"未披露"）。新提示词明确禁止推断原因、后果与动机，禁止写"某信息未披露"，改为 1–2 句，并加 1–2 个示范；
     - 用同一批 50 条真实新闻对比新旧提示词的加料率，选更好的一版；
     - 放量后随机抽查 100 条，记录引入原文以外信息的比例与类型，写进报告；
     - 摘要再用任务 3 的各模型做嵌入。
  5. 股票-日聚合：主口径对同一 (trade_date, ticker) 的多篇新闻嵌入取均值，同时记录 `news_cnt`、`has_news` 与该日新闻中有时刻记录的占比；对照口径为"每篇单独预测，再按股票-日对预测取均值"。
  6. 全维 Ridge（充分统计量写法）：
     - 按年累加 X′X、X′1、X′y、y′1（float64）。所有标签在同一遍计算中完成：主标签、建仓推迟 1–4 天的收益、收盘到收盘收益、16:00 截止版本的标签；同时按 `time_precision` 子集分别累加一份；
     - 读取嵌入分片时按年先拷到容器盘再计算（网络卷顺序读带宽有限）；
     - 每个滚动窗口：训练年的统计量相加 → 中心化 → 对 X′X 做一次特征分解 → 一次写出整个 λ 网格的解 → 在验证年选 λ → 输出测试年的样本外预测；
     - 对每种文本 × 每个嵌入模型重复。
  7. PCA：只在 2015–2018 年的数据上拟合一次。这段时间早于所有验证期与测试期，对每个滚动窗口都没有泄漏。导出 256 维（MLP 与随机森林用）与 64 维（Qlib 用）特征；记录累计解释方差，并检查第一主成分是否只在度量文本长度。
  8. 弱文本基线：Loughran-McDonald 词典的正负词计数差作为情绪分；TF-IDF（最多 5,000 维）+ Ridge，同样按年度滚动。
  9. 健全性检查：抽几条新闻看最近邻是否语义相近；比较同一新闻在不同模型下预测值的相关性。
- 验收：嵌入覆盖率表（每种文本 × 每个模型 × 精度子集）；摘要抽查记录；各模型 × 各文本的样本外 IC 初表；卷上产物清单与校验和。
- 云端耗时与费用见第 5 节。

**模块 4：Qlib 数据集与 Handler（云端）**

- 目标：三套可直接被 Qlib Model 消费的数据集：纯量价、纯文本、融合；并把全维 Ridge 的预测接入 Qlib 的记录与回测流程。
- 任务：
  1. 特征入库，二选一。方式 A：把 64 维 PCA 嵌入（`$emb_0` … `$emb_63`）、`news_cnt`、`has_news` 与价格合并到同一组 CSV 后重新 `dump_all`，之后可在表达式中直接写 `$emb_0`、`Mean($emb_0, 5)`。方式 B：用 `StaticDataLoader` 读取 parquet，再用 `NestedDataLoader` 与 Alpha158 的 `QlibDataLoader` 拼接。先用 A。
  2. Handler：继承 `DataHandlerLP`。推断期处理器用 `RobustZScoreNorm`（截面标准化、裁剪离群值）与 `Fillna`；学习期处理器用 `DropnaLabel` 与 `CSRankNorm`（标签截面排名化）。无新闻的股票-日把嵌入填 0，并靠 `has_news` 区分。
  3. 标签：主口径 `Ref($open,-2)/Ref($open,-1)-1`，即 t+1 开盘买入、t+2 开盘卖出，与 9:00 ET 截止一致。副口径 `Ref($close,-2)/Ref($close,-1)-1`。
  4. 切分：年度滚动（4 年训练、1 年验证、1 年测试），测试期 2020–2023，共 4 组 segments；用 Qlib `RollingGen` 或自写循环生成。每组的标准化统计量只用该组训练期拟合。
  5. 外部预测接入：写一个读取 Ridge 预测文件的 Model 封装（`fit` 为空，`predict` 返回对应 segment 的预测），让全维 Ridge 的预测也走 SignalRecord、SigAnaRecord、PortAnaRecord。
  6. YAML：`baseline_alpha158.yaml`、`news_only.yaml`、`fusion.yaml` 只在 handler 部分有差异；另加 `external_ridge.yaml`。
- 验收：`dataset.prepare("train")` 返回的列数、缺失率符合预期；四个 YAML 均能被 `qrun` 加载；外部预测在 Qlib 中算出的 IC 与模块 3 算出的一致。

**模块 5：模型训练（云端）**

- 目标：两张主结果表。
- 任务：
  1. 表 A（复现原文）：文本表示 {LM 词典, TF-IDF, MiniLM, FinBERT, ChronoBERT, LLaMA3-8B} × 文本类型 {标题, 原文, 摘要}，模型统一为全维 Ridge。指标为日均 IC、等权与市值加权五分位多空夏普；模型之间做 Diebold-Mariano 检验。按"全样本 / 有时刻子集 / 仅日期子集"三栏报告。
  2. 表 B（Qlib 增量检验）：特征 {Alpha158, 新闻 PCA-64, 融合} × 模型 {Ridge, LightGBM, MLP}，每组至少 3 个随机种子：
     - Ridge：`qlib_ext/models.py` 中封装 sklearn `Ridge`（用于 PCA 特征），正则强度在验证年上选；
     - LightGBM：`qlib.contrib.model.gbdt.LGBModel`，`num_leaves` 31–63、学习率 0.02–0.05、`feature_fraction` 0.8、验证集早停，16 线程。报告中注明原文未用提升树；
     - MLP：`qlib.contrib.model.pytorch_nn.DNNModelPytorch`，2–3 层、每层 256 单元、dropout 0.3，在 L40S 上训练。
  3. 非线性复现（对应原文表 7）：在 LLaMA3-8B 原文嵌入的 PCA-256 特征上训练 MLP 与随机森林（树的数量 500 以内、`min_samples_leaf` 100），与全维 Ridge 比较。
  4. 调参：Optuna 以验证年 Rank IC 为目标，每个模型 20 次试验以内；测试期只评估一次。
  5. 记录：每次训练用 `R.start(experiment_name=...)` 包裹，`SignalRecord` 保存预测，`SigAnaRecord` 计算 IC、ICIR、Rank IC、Rank ICIR。MLflow 目录放在卷上。
- 验收：表 A、表 B（指标均值与标准差）；纯文本模型的 IC 显著异于 0 是后续分析的前提。

**模块 6：回测与分析（云端；作图可在 Mac）**

- 目标：把预测转成可比较的组合表现，完成论文的核心分析。
- 任务：
  1. 五分位多空（主）：每日按预测值分五组，做多最高组、做空最低组，等权与市值加权，开盘到开盘、日频换仓，用 pandas 自写实现。十分组作为稳健性检验。
  2. 交易成本与换手：按原文成本模型，每 100% 换手扣 10 bps；用 EWCT 控制换手（每日只调整 ω 比例的仓位，ω 取 0.1–0.9），报告换手率、毛夏普与净夏普（对应原文表 8）。另画 0/5/10/20 bps 的成本敏感性曲线。
  3. Qlib 多头回测（补充）：`TopkDropoutStrategy`（topk 50、n_drop 5），`deal_price: open`，基准 SPY；`PortAnaRecord` 输出年化超额、信息比率、最大回撤、换手。
  4. 新闻动量：建仓推迟 k 天（k = 1…5）的多空表现（对应原文表 18）；预测值对 1、2、3、5、10 日后收益的 IC 衰减曲线。第一天效应只在有时刻子集上检验，仅日期子集的结果单列。
  5. 规模分组：S&P 500 内按市值分三组，报告 IC 与多空收益，检验"规模越小信号越强"。
  6. 文本形式：标题 vs 原文 vs 摘要（对应原文表 16），在正文可用的子集上比较。
  7. 稳健性：16:00 ET 截止版本；收盘到收盘成交（对应原文附录表 IA9）；单篇预测再聚合的口径；十分组。
  8. 新闻新鲜度：比较"当日有新闻"与"嵌入前向填充 5 日"两种特征下的 IC。
  9. 否定词子样本：标题或正文含 not、no、never、miss、fail 等词的子样本中，比较词典情绪分与 LLM 嵌入的 IC。
  10. 短期反转对照（可选）：过去 5 日收益与新闻预测的 5×5 双重排序，检验新闻信号不是反转信号的变形（对应原文表 17 与图 9）。
  11. 图表：累计多空收益（含成本）、分组收益柱状图、IC 时序、衰减曲线、成本与换手曲线，用 `qlib.contrib.report` 与 matplotlib 产出。数字表与图存入仓库 `results/`，是唯一需要回传本地的产物。
- 验收：分析脚本可从 `pred.parquet` 从头运行；每张图都有对应的数字表。

**模块 7：扩展实验**

- 时间一致模型对照（亮点）：同一流水线、同一测试期，比较按年滚动的 ChronoBERT、LLaMA3-8B（知识截止 2023 年 3 月，覆盖测试期）、FinBERT 与 MiniLM；按测试年拆分，看差异是否集中在某些年份；结合模块 3 的摘要抽查结果。若几者接近，说明前视偏差影响有限；若 LLaMA3 明显更好，需讨论差距中有多少来自模型能力、多少可能来自预训练语料覆盖了测试期。无论哪种结果都是可报告的发现。
- 替代新闻源（可选，美股主线完成后考虑）：
  - Alpaca News API（Benzinga 提供）：免费账户即可调用，历史回溯到 2015 年，时间戳精确到秒并带时区，可返回正文，按 symbols 过滤、每页最多 50 条、免费档限速约每分钟 200 次。它能让 9:00 ET 规则覆盖全部记录，并把测试期延伸到 2024–2026 做知识截止日后的样本外检验（对应原文表 13）。条款不允许再分发，仓库只放抓取脚本。
  - `financial-news-multisource`（Hugging Face，需申请）：24 个公开新闻集的 parquet 聚合，含 FNSPID 子集并带精度标记与交易日锚点；可作便利镜像。
  - Drinkall 的 Yahoo Finance 数据（5.1 万篇，2017–2023，分钟级，带 ticker）：只够做跨来源一致性检查。
  - EDGAR 8-K 新闻稿：免费、受理时间精确到秒、按公司归属；不是新闻而是公告，可作精确时间戳的补充实验。
- 模型集成（可选）：多个嵌入模型的标准化预测取均值，对应演讲中"集成优于单一最优模型"的说法；注明原文图 7 显示各 LLM 组合高度相关。
- ChatGPT 嵌入（可选）：OpenAI text-embedding-3-large。需要在 platform.openai.com 单独开通 API 并预充值，ChatGPT 订阅不含 API 额度。用 Batch API（价格为同步接口的一半，24 小时内返回；单个批次最多 5 万条输入、文件不超过 200MB）。文本与截断规则和其他模型一致，用 tiktoken 截断到 512 token。基准情景费用约 73 美元。结果永久保存，记录模型名与调用日期。
- Llama-3.2 1B / 3B 规模梯度（可选，低优先级）：与 LLaMA3-8B 共用词表，算力约为半个 8B 任务，基准情景约 12 美元。
- 不做 LLaMA2-13B：它与 LLaMA3-8B 不只是参数量不同，训练数据与词表也不同，比较结果无法归因到规模；原文中 LLaMA2-13B 的等权多空夏普（4.36）反而低于 LLaMA3-8B（4.59），顶层模型之间的差异也不显著。
- 港股迁移（最低优先级）：用恒生指数成分股与 akshare/yfinance 日线重复模块 1–6。英文新闻覆盖较少，印花税自 2023-11-17 起买卖双方各 0.1%，成本假设需相应提高。

**模块 8：报告、仓库与简历**

- README 结构：动机与论文摘要 → 数据实况与对齐规则（含时区校验记录、精度分布）→ 方法与配置 → 算力与成本 → 主结果表 → 核心分析 → 扩展实验 → 局限性与下一步 → 复现步骤。
- 复现性：`make` 入口覆盖全流程（模块 0 已有 `make check-env`、`make verify-llama`、`make smoke`、`make lock`、`make test`；2026-10-24 起 `make help` 列出全部 47 个目标，覆盖模块 1–8：`universe`/`prices`/`market-cap`、`news-*`/`tz-check`、`embed*`/`summarize`/`bow`/`pca`、`labels`/`aggregate`/`ridge`/`table-a`/`downstream`、`qlib-news-dump`/`table-b`/`incremental`/`external-backtests`、`longshort`/`dm-test`/`decomposition`/`freshness`/`analyze`、`dev-sample`/`backup`）；固定随机种子；`requirements-main.txt` 与 `requirements-vllm.txt` 各一份锁定版本。
- 数据归档：分析阶段结束前，把全维嵌入、摘要与 Ridge 统计量用 rclone 备份到对象存储（Backblaze B2 / Cloudflare R2 之类），之后删除网络存储卷。
- 合规：FNSPID 的两种许可表述都写明；仓库只放处理脚本与结果，不重新分发原始新闻与摘要全文；LLaMA3 的使用遵守 Meta Llama 3 社区许可。
- 简历条目按第 8 节模板填数字。

## 5. 算力、存储、工作流与预算

**5.1 分工原则：计算全在云端，开发按工作性质分在两处**

| 位置 | 做什么 | 存什么 |
| --- | --- | --- |
| 云端（RunPod，一台固定配置） | 全部计算：价格数据、新闻全量清洗、嵌入、摘要、全维 Ridge、PCA、Qlib 建模、LightGBM / MLP / 随机森林、回测与分析；以及需要真实数据、GPU 或 Qlib 才能验证的代码开发与调试（Pod 上的 Claude SSH 会话） | 原始数据、清洗后文本、模型权重、全维嵌入、摘要、预测、Qlib 数据、MLflow 记录、仓库工作副本（网络存储卷 250GB） |
| 本地（MacBook Air） | 纯逻辑代码、单元测试（`dev_data/` 小样本）、文档与规划、最终作图（Claude 本地会话）；也可以用 `ssh runpod '...'` 在 Pod 上执行命令 | 仓库、开发样本（< 2GB）、`results/` 中的表格与图（< 2GB） |

不再有"把中间产物下载到本地"这一步。需要新的标签或子样本时，直接在云端重算（卷还在时开机约半小时，约 1 美元）；因此模块 3 一次性算完所有已知标签的统计量，卷保留到分析阶段结束。

**5.2 RunPod 固定配置**

原则：一套配置覆盖全部阶段，存成自定义模板，以后每天只做一件事——从模板部署。

| 项目 | 固定值 | 理由 |
| --- | --- | --- |
| 云类型 | Secure Cloud，按需实例（不用 Spot） | 网络存储卷只能挂在 Secure Cloud；按需实例不会被中断 |
| GPU | 1 × L40S 48GB | 48GB 放下 LLaMA3-8B bf16 权重（16GB）后还有 30GB 给 vLLM 的 KV cache；Ada 架构吞吐约为 A40 / A6000 的 2.4 倍，价格只高 1.85 倍，单位工作量更便宜 |
| 配套 vCPU / 内存 | 定价页标 16 vCPU / 94GB；实测宿主机不同配额不同（一台为 17.85 核 / 125GB） | 48GB 档位里 vCPU 最多的一档；清洗去重、LightGBM、Alpha158 表达式计算都吃 CPU。线程数由 `env.sh` 按 cgroup 配额自动设置（`$NCPU`），内存按 94GB 预算 |
| 容器盘 | 100GB | 运行时与高速暂存，Pod 停止即清空；Ridge 阶段按年把嵌入分片拷到容器盘再计算 |
| 网络存储卷 | `llm-news-vol`，US-IL-1，250GB，Standard 档，每 GB 每月 0.07 美元 | 容量只能扩不能缩，不够再扩；它是 MooseFS 网络文件系统，`df` 显示的是整个集群，用量看控制台 Storage 页 |
| 模板 | `llm-news-l40s`：官方 Runpod PyTorch 镜像（torch 2.8.0+cu128）另存，容器盘 100GB，网络卷挂载到 `/workspace`，暴露 TCP 22 与 HTTP 8888 | 自带 SSH over TCP 与 JupyterLab；模板里的环境变量 SSH 会话读不到，实际由 `env.sh` 注入；vLLM 装在独立 venv 里 |
| 价格 | 每小时 1.09 美元（2026-10-08 定价页） | 以控制台实时价格为准 |
| 唯一备选 | RTX 6000 Ada 48GB（167GB 内存、10 vCPU，每小时 0.99 美元） | L40S 缺货时使用；同为 Ada 架构、同为 48GB，代码与环境一行不改，只在部署时换 GPU 下拉项 |

不选其他档位的原因：A40 / A6000（0.59 美元）是 Ampere 架构，吞吐只有 L40S 的四成，批处理总费用相近但墙上时间翻倍，50GB 内存、9 vCPU 在清洗和 Qlib 阶段明显变慢；A100 80GB（1.79 美元）的显存 8B 模型用不满；24GB 档（4090、3090、L4）跑 vLLM 批量摘要时 KV cache 太小。

**5.3 本地配置（MacBook Air）**

- Claude Desktop：Code 标签的本地会话，以及连接 Pod 的 SSH 会话（连接名 `runpod-l40s`，SSH host 填 `runpod`，项目文件夹 `/workspace/repo`）。
- Python 3.12 轻量环境（`requirements-dev.txt`：numpy、pandas、polars、duckdb、pyarrow、pyyaml、pytest、matplotlib、jupyter）。不装 torch、不装 Qlib。
- `~/.ssh/config` 的 `Host runpod` 条目（模板见 `infra/ssh_config.example`，含 `StrictHostKeyChecking no`、`UserKnownHostsFile /dev/null`、`LogLevel ERROR`、`ServerAliveCountMax 10`）；`runpod-set <IP> <PORT>` 一行更新 IP 与端口。
- GitHub：`gh auth login` 登录（HTTPS）。
- 磁盘占用控制在 5GB 以内：仓库、开发样本、`results/`。

**5.4 工作流（Claude Code 辅助）**

代码的唯一真相源是 GitHub 仓库；数据的唯一真相源是网络存储卷；Pod 是一次性的计算容器。仓库工作副本 `/workspace/repo` 在网络卷上，Terminate Pod 不会丢失未提交的改动，但仍要求及时提交。

Claude Code 的两种会话，按工作性质分工：

| 会话 | Claude Code 跑在哪 | 文件与 GPU 在哪 | 用途 |
| --- | --- | --- | --- |
| Claude Desktop 本地会话 | Mac | Mac 上的仓库与 `dev_data/` 样本 | 纯逻辑代码、单元测试、文档、规划、作图；需要时用 `ssh runpod '...'` 在 Pod 上执行命令、查看日志 |
| Claude Desktop SSH 会话 | RunPod Pod 上 | `/workspace` 的数据、GPU 与 Qlib | 需要真实数据、GPU 或 Qlib 才能验证的代码（解析、对齐、嵌入、Handler、回测）的编写与调试；启动和监控实验 |

SSH 会话的要点：Desktop 首次连接时要从 Mac 上传助手程序，本地上行慢时可能等很久；部署结果在 `/workspace/.claude/remote`（`~/.claude` 链接到卷上），换 Pod 后可以复用，Desktop 更新后可能需要重新部署。登录用的是 Desktop 里的 Claude 账户，Pod 里不需要单独登录。两种会话的历史不共享，交接靠 `CLAUDE.md`、`docs/plan.md`（本计划）、git 提交信息和 `docs/worklog.md`。

协作规则（写进 `CLAUDE.md`）：

1. 同一时间只在一边改代码。
2. 开始工作前先 `git pull`；告一段落就 commit 并 push，WIP 提交也可以。
3. `tests/` 下的单元测试必须能在 Mac 上用 `dev_data/` 样本或手写小例子跑通，不能依赖 `/workspace`。
4. Terminate Pod 之前确认 `git status` 干净并且已经 push。

每次开工（5 分钟）：

1. RunPod 控制台 Pods → Deploy：先选网络卷 `llm-news-vol` → GPU 选 L40S（缺货时换 RTX 6000 Ada）→ 模板 `llm-news-l40s` → Deploy On-Demand。
2. Connect → "SSH over exposed TCP" 拿到本次 Pod 的公网 IP 和端口，在 Mac 上执行 `runpod-set <IP> <PORT>`。
3. `ssh runpod 'bash /workspace/bootstrap.sh'`（约 1 分钟）。
4. 需要时在 Claude Desktop 里打开 SSH 会话 `runpod-l40s`。

长任务：

- 超过 5 分钟的任务一律用 `bash infra/run_bg.sh <job> <cmd...>` 启动（`setsid nohup`，日志写到 `/workspace/logs/<job>_<时间戳>.log`），按 news_id 或年份分片写出、支持断点续跑。Claude 会话只负责启动和 `tail` 日志：以 Claude 账户登录时，Desktop 断开后会话的登录可能过期，不能靠会话维持长任务。
- 跑完立即 Terminate Pod，数据留在卷上。

收工：

- `results/` 里的表格与图 commit 进仓库；Pod 上只提交 `results/` 小文件、lock 文件与代码改动。
- 结束 Desktop 的 SSH 会话 → 确认 `git status` 干净且已 push → Terminate Pod（不用 Stop）。
- 大产物在分析阶段结束时备份到对象存储，然后删卷。

`CLAUDE.md` 必须写明的规则：两种会话的分工与协作规则；资源约束（`$NCPU`、94GB 内存预算、网络卷读写特性）；目录约定与三个接口文件的格式；大文件不进 git；长任务必须用 `run_bg.sh` 并分片写入；删除 `/workspace/data`、`/workspace/hf_cache`、`/workspace/qlib_data` 需确认；不打印密钥；vLLM 脚本的环境变量；前视偏差红线；每次会话结束更新 `docs/worklog.md`。

**5.5 云端耗时估算（L40S，粗估）**

| 任务 | 耗时 |
| --- | --- |
| LLaMA3-8B 原文嵌入（前 512 token） | 每 100 万篇约 11 小时 |
| LLaMA3-8B-Instruct 摘要生成（vLLM） | 每 100 万篇约 12–13 小时 |
| 摘要嵌入 | 每 100 万篇约 2.5 小时 |
| 标题嵌入 | 每 100 万条约 1 小时 |
| ChronoBERT 滚动版本 + FinBERT + MiniLM | 合计约 3–5 小时 |
| 全量新闻清洗 | 约 1 小时 |
| 全维 Ridge 与 PCA | 约 2–4 小时 |
| Qlib 基线、融合模型、MLP、回测与分析 | 约 10–15 小时 |
| 环境搭建、吞吐实测与调试 | 约 12 小时 |

以上整体再加 30% 余量。估算依据：每篇约 450 token、计算量约为 2 × 参数量 × token 数、GPU 利用率约五成。模块 0 的初测（11,144 tokens/s，约合每 100 万篇 11.2 小时）与估算一致；正式数字以模块 3 任务 1 在真实新闻上的实测为准。

**5.6 预算**

新闻条数要在模块 2 统计后才能确定，先按三种情景估算（美元，粗估，L40S 1.09 美元/小时）：

| 情景 | 新闻规模 | 批处理 GPU 小时 | 批处理费用 | Pod 上的开发与 Qlib 实验 | 存储（250GB × 3 个月） | 合计 |
| --- | --- | --- | --- | --- | --- | --- |
| 低 | 150 万条，其中 100 万带正文 | 约 65 | 约 70 | 约 50 小时 ≈ 55 | 约 53 | 约 180 |
| 基准 | 300 万条，其中 200 万带正文 | 约 105 | 约 115 | 约 60 小时 ≈ 65 | 约 53 | 约 235 |
| 高 | 600 万条，其中 400 万带正文 | 约 180 | 约 195 | 约 90 小时 ≈ 100 | 约 53 | 约 350 |

容器盘 100GB 按运行小时计费，折合每小时约 0.014 美元，忽略不计。可选加项：ChatGPT 嵌入（低 / 基准 / 高情景约 37 / 73 / 146 美元）；Llama-3.2 规模梯度（基准情景约 12 美元）。

**5.7 控制费用的做法**

- 费用的杠杆是 Pod 的开机小时数，不是 GPU 型号：不需要数据、GPU 或 Qlib 的工作（纯逻辑、单元测试、文档、规划）在 Mac 上做；Pod 只在需要真实数据时开，空闲就 Terminate。
- 上云后第一件事是实测吞吐，按实测修正预算再放量。
- 长任务后台运行、分片写入；跑完立即停 Pod。
- 账户保持余额并设提醒：余额不足时 RunPod 会自动停掉 Pod。
- 分析阶段结束、产物备份后，删除网络存储卷。

## 6. 代码仓库结构与关键实现细节

仓库按流水线阶段分目录，实验只通过 YAML 切换。

仓库：[github.com/dingtao-shen/llm-news-alpha](https://github.com/dingtao-shen/llm-news-alpha)（私有）。Pod 上的工作副本在 `/workspace/repo`。

```text
llm-news-alpha/
├── infra/                      # 模块 0（已完成）
│   ├── bootstrap.sh            # 每次开 Pod 后执行；幂等
│   ├── env.sh                  # 所有 shell 最先加载：路径、线程数、密钥、venv-main
│   ├── run_bg.sh               # 长任务后台启动器（setsid nohup，日志写到 /workspace/logs）
│   ├── check_env.sh            # 配额、GPU、import 耗时体检
│   ├── verify_llama.py         # 核对卷上 LLaMA 3 权重的 commit 与 SHA-256
│   ├── smoke_embed.py          # LLaMA3-8B 10 条文本嵌入 + 吞吐
│   ├── smoke_vllm.py           # LLaMA3-8B-Instruct + vLLM 10 条摘要
│   ├── ssh_config.example      # Mac 上 Host runpod 的模板
│   └── runpod_template.md      # RunPod 固定配置、开工收工步骤、卷上固定位置
├── data/                       # 模块 1
│   ├── build_universe.py       # 时点成分股 → instruments/sp500.txt
│   ├── download_prices.py      # yfinance 限速下载、复权因子、缓存
│   ├── market_cap.py           # SEC 历史流通股数 → 近似市值
│   └── dump_qlib.sh            # 调用 scripts/dump_bin.py
├── news/                       # 模块 2
│   ├── parse_fnspid.py         # 全字符串读取、正规 CSV 解析、news_id、语言过滤
│   ├── source_stats.py         # 来源 / 精度 / 正文可用率统计
│   ├── validate_timezone.py    # 抽样抓 URL 校验时区与日期约定
│   ├── filters.py              # 长度、近似重复
│   ├── align.py                # 分层对齐（9:00 主口径、16:00 稳健口径）
│   ├── build_clean.py          # 标准新闻表 → 日期修正 → 对齐 → 过滤 → news_clean.parquet
│   ├── candidates.py / ticker_map.py / news_id.py / schema.py
│   └── sources/                # 数据源适配器（fnspid.py；以后 alpaca.py）
├── text/                       # 模块 3
│   ├── benchmark.py            # 各模型吞吐实测
│   ├── embed.py                # LLaMA3-8B / ChronoBERT / FinBERT / MiniLM 均值池化嵌入
│   ├── summarize_vllm.py       # LLaMA3-8B-Instruct 批量摘要（venv-vllm）
│   └── bow_baseline.py         # LM 词典情绪分、TF-IDF + Ridge
├── models/                     # 模块 3
│   ├── ridge_suffstats.py      # 按年累加统计量、滚动 Ridge、样本外预测
│   └── pca_export.py           # PCA-256 / PCA-64 导出
├── qlib_ext/                   # 模块 4–5
│   ├── handler.py              # NewsAlpha158Handler(DataHandlerLP)
│   └── models.py               # RidgeModel、ExternalPredModel
├── configs/                    # 模块 1、4
│   ├── baseline_alpha158.yaml
│   ├── news_only.yaml
│   ├── fusion.yaml
│   └── external_ridge.yaml
├── analysis/                   # 模块 6
│   ├── longshort.py            # 五分位多空（等权 / 市值加权）、EWCT、成本
│   ├── decay_size_fresh.py     # 延后建仓、规模分组、新鲜度、否定词、精度子集
│   ├── text_type.py            # 标题 / 原文 / 摘要对比
│   └── report.ipynb
├── tests/                      # pytest，Mac 上能跑：解析、过滤、对齐等
├── results/                    # 表格与图（小文件，进 git）
├── docs/
│   ├── plan.md                 # 本计划
│   └── worklog.md              # 每次会话的交接记录
├── CLAUDE.md                   # 给 Claude Code 的工作约定
├── Makefile                    # make help 列出全部目标
├── paths.yaml                  # 所有数据路径
├── pytest.ini
├── requirements-main.txt / requirements-main.lock    # venv-main（Pod）
├── requirements-vllm.txt / requirements-vllm.lock    # venv-vllm（Pod）
├── requirements-dev.txt        # Mac 轻量环境
└── README.md
```

各模块的目录目前只有 `__init__.py`，实现时按上面的文件名补上；`Makefile` 里后续模块的目标先以注释占位。

**卷上的固定位置**

| 路径 | 内容 |
| --- | --- |
| `/workspace/repo` | 仓库工作副本 |
| `/workspace/env.sh`、`/workspace/bootstrap.sh` | 由 bootstrap 从仓库安装 |
| `/workspace/.secrets/env` | 密钥（权限 600，永不进 git） |
| `/workspace/venv-main`、`/workspace/venv-vllm` | 两个虚拟环境 |
| `/workspace/src/qlib` | Qlib 源码（editable 安装，含 `scripts/dump_bin.py`） |
| `/workspace/hf_cache` | Hugging Face 模型缓存 |
| `/workspace/.cache/vllm` | vLLM 的 torch.compile 缓存 |
| `/workspace/data`、`/workspace/qlib_data`、`/workspace/mlruns`、`/workspace/logs` | 数据、Qlib 二进制、MLflow、日志 |
| `/workspace/.claude`、`/workspace/.claude.json` | Claude Code 配置与 SSH 会话的远程部署（`~` 下是指向这里的符号链接） |

**分层对齐（news/align.py 的核心）**

```python
import pandas as pd

def feature_day(ts_et: pd.Timestamp, precision: str, calendar: pd.DatetimeIndex,
                cutoff="09:00") -> pd.Timestamp:
    """返回这条新闻归入的特征日 t；在 t 之后的第一个交易日开盘建仓。
    ts_et: 美东时间戳（仅日期的记录传入当日 00:00）；precision: 'second' 或 'day'。"""
    if precision == "day":
        ts_et = ts_et.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
    h, m = map(int, cutoff.split(":"))
    # 第一个满足 "ts_et 早于当日 cutoff" 的交易日 d
    days = calendar[calendar >= ts_et.normalize()]
    d = days[0] if ts_et < days[0] + pd.Timedelta(hours=h, minutes=m) else days[1]
    # 特征日 = d 的前一个交易日
    return calendar[calendar < d][-1]
```

**Handler 配置示例（fusion.yaml 中的 handler 部分，方式 A 入库）**

```yaml
handler:
  class: NewsAlpha158Handler
  module_path: qlib_ext.handler
  kwargs:
    start_time: 2015-01-01
    end_time: 2023-12-31
    fit_start_time: 2015-01-01   # 每个滚动窗口改为该窗口的训练期
    fit_end_time: 2018-12-31
    instruments: sp500
    n_emb: 64                    # $emb_0 … $emb_63，PCA 只在 2015–2018 拟合
    label: ["Ref($open, -2) / Ref($open, -1) - 1"]   # 与 9:00 ET 截止对应
    infer_processors:
      - {class: RobustZScoreNorm, kwargs: {fields_group: feature, clip_outlier: true}}
      - {class: Fillna, kwargs: {fields_group: feature}}
    learn_processors:
      - {class: DropnaLabel}
      - {class: CSRankNorm, kwargs: {fields_group: label}}
```

`NewsAlpha158Handler` 在 `get_feature_config()` 中把 Alpha158 的表达式列表与 `["$emb_%d" % i for i in range(n_emb)] + ["$news_cnt", "$has_news"]` 拼接；`news_only.yaml` 只传后者。

**充分统计量 Ridge（models/ridge_suffstats.py 的核心）**

```python
import numpy as np

def ridge_path(XtX, Xsum, Xty, ysum, n, lambdas):
    """由累加统计量求中心化 Ridge 的整条 λ 路径。
    XtX: P×P，Xsum: P，Xty: P，ysum: 标量，n: 样本数；全部用 float64 累加。"""
    mu, ybar = Xsum / n, ysum / n
    S = XtX - n * np.outer(mu, mu)        # Σ(x-μ)(x-μ)'
    s = Xty - n * mu * ybar               # Σ(x-μ)(y-ȳ)
    w, V = np.linalg.eigh(S)              # 每个窗口只分解一次
    z = V.T @ s
    betas = [V @ (z / (w + lam)) for lam in lambdas]
    intercepts = [ybar - mu @ b for b in betas]
    return betas, intercepts
```

某个滚动窗口的训练统计量等于该窗口内各年统计量之和；λ 只在该窗口的验证年上选，网格范围参考原文脚注 18。

**模型封装（qlib_ext/models.py）**

```python
import pandas as pd
from qlib.model.base import Model
from sklearn.linear_model import Ridge

class RidgeModel(Model):
    """用于 PCA 特征的 Ridge。"""
    def __init__(self, alpha=1.0):
        self.model = Ridge(alpha=alpha)
    def fit(self, dataset):
        x, y = dataset.prepare("train", col_set=["feature", "label"], data_key="learn")
        self.model.fit(x.values, y.values.ravel())
    def predict(self, dataset, segment="test"):
        x = dataset.prepare(segment, col_set="feature", data_key="infer")
        return pd.Series(self.model.predict(x.values), index=x.index)

class ExternalPredModel(Model):
    """读取全维 Ridge 的样本外预测，接入 Qlib 的记录与回测流程。"""
    def __init__(self, pred_path):
        self.pred = pd.read_parquet(pred_path)["score"]   # 索引为 (datetime, instrument)
    def fit(self, dataset):
        pass
    def predict(self, dataset, segment="test"):
        idx = dataset.prepare(segment, col_set="feature", data_key="infer").index
        return self.pred.reindex(idx)
```

**回测配置要点（port_analysis_config）**

```yaml
strategy:
  class: TopkDropoutStrategy
  module_path: qlib.contrib.strategy
  kwargs: {signal: <PRED>, topk: 50, n_drop: 5}
backtest:
  start_time: 2020-01-01
  end_time: 2023-12-31
  account: 100000000
  benchmark: SPY
  exchange_kwargs:
    deal_price: open
    open_cost: 0.0005     # 单边 5 bps，买卖一轮合计 10 bps；敏感性分析中修改
    close_cost: 0.0005
    min_cost: 0
    limit_threshold: null
```

**容易做错的九个实现点**

1. PCA 与标准化统计量只在训练期拟合：PCA 只用 2015–2018；`RobustZScoreNorm` 的 `fit_start_time` 与 `fit_end_time` 在每个滚动窗口都要显式设为该窗口的训练期。
2. 嵌入缓存以 news_id 为键，而不是以 (ticker, date) 为键，否则对齐规则一改就要全部重算。
3. `deal_price: open` 配合开盘到开盘标签；若改用收盘到收盘标签，`deal_price` 也要改为 close，否则回测与 IC 不在同一口径。
4. 无新闻的股票-日填 0 之后，`has_news` 必须进入特征，否则模型无法区分"中性新闻"与"没有新闻"。
5. 9:00 截止与标签必须对应：特征日 t 包含截至 t+1 日 9:00 的新闻，所以标签必须是 t+1 开盘到 t+2 开盘。若错写成 t 开盘到 t+1 开盘，就用到了未来新闻。
6. 仅日期记录的时间戳一律视为当日 23:59，绝不能视为 00:00；后者会把盘后发布的新闻算进当天开盘，引入前视偏差。
7. 时区校验未通过的来源，其时刻全部作废，降级为仅日期处理。
8. 充分统计量 Ridge：用中心化后的统计量求解，截距单独还原；累加一律用 float64，避免数值误差。
9. 每个滚动窗口的 λ 只在该窗口的验证年上选，测试年只评估一次。

## 6.1 数据源无关的接口约定（2026-10-23 增补）

决定：先用 FNSPID 把整条流水线跑通并出报告，换数据源留作后续迭代。为此把"数据源特定"的部分压缩到一个适配器里：

- **接口文件 0：标准新闻表** `embed_candidates.parquet`（`news/schema.py` 的 `STANDARD_NEWS`）：news_id、ticker、ts_utc、has_time、title、body、has_body、url、source、dataset。
  任何新闻源的适配器（`news/sources/<src>.py`）只负责产出它；FNSPID 的适配器是 `news/sources/fnspid.py`（解析 + 低成本过滤）。
- 之后的 嵌入（`text/embed.py`）、日期修正与对齐（`news/build_clean.py`）、聚合（`models/aggregate.py`）、Ridge、回测 全部只读接口文件，不碰任何源特定字段。
- 嵌入分片支持增量：`text/embed.py --delta <tag>` 只嵌入目录里尚无嵌入的 news_id，写 `delta-<tag>-part-*.parquet`；读取方按 `*part-*.parquet` 读全部。
  换源后或补 ticker 别名后只需嵌新来的新闻（2026-10-23 用它补了 BRK.B 的 1,680 条）。
- 带 `{dataset}` 的路径按数据集分目录（`paths.yaml` 的 `dataset`，环境变量 `DATASET` 覆盖）：`/workspace/data/<dataset>/{news,emb,agg,preds}`；价格、Qlib、标签、市值与数据集无关。
- `make downstream`：从 news_clean 重跑 聚合 → Ridge → 表 A → 多空 → DM → 信号拆分 → λ 敏感性，换源后一条命令。
- `tests/test_interfaces.py` 对三个接口文件与标准新闻表做 schema 断言（有 dev 样本时对真实样本检查）。

**FNSPID 日期修正**（`news/build_clean.py` 的 `DATE_FIXES`，依据 `results/news/tz_check_conclusions.md`）：Benzinga 有时刻记录的时间戳是 UTC−8，统一 +8 小时；
nasdaq.com 的全部有时刻记录（都标 2023-12-16，实为抓取时间）与 2023-11-30..12-16 的抓取期打标记录剔除；nasdaq.com 日期取 FNSPID 与 URL 日期中较晚者。

## 6.2 阶段计划（2026-10-23 起）

| 阶段 | 内容 | 产出 |
| --- | --- | --- |
| 0 收口与接口维护（完成） | 日期修正并重跑下游；6.1 节的接口约定；BRK.B 增量嵌入 | 修正后的表 A、多空表；可换源的接口 |
| B 补齐表 A | AI 摘要（改提示词 → 50 条对比 → 放量 → 100 条抽查 → 4 个模型嵌入）；LM 词典 + TF-IDF 基线；PCA-256/64；16:00 口径 | 表 A 完整版（含 DM 检验） |
| C Qlib 融合（模块 4–5） | PCA-64 入库、`NewsAlpha158Handler`、滚动 segments、外部预测封装；表 B：{Alpha158, 新闻, 融合} × {Ridge, LightGBM, MLP}；克制调参；反转单因子对照 | 表 B、增量检验 |
| D 模块 6 其余 | 市值加权、十分组、建仓推迟衰减、规模分组、文本形式、否定词、新鲜度、Qlib 多头、低换手持仓 | 图 1–4、稳健性表 |
| E 模块 7 | 时间一致性对照成稿；"隔夜兑现"分解为核心发现；不做 ChatGPT 嵌入与 Llama-3.2 梯度 | 差异化点正式结果 |
| F 模块 8 | README 报告、make 入口核对、dev 样本、备份、删卷 | 公开仓库与报告 |
| G（以后）换源 | 新写 `news/sources/<src>.py`，`DATASET=<src> make downstream` | 对照实验 |

实测修正预期：纯文本信号的日均 Rank IC 在 0.000–0.010，低于原先预期的 0.5–1%；嵌入含强情绪信息（对新闻当天收益 Rank IC 0.10–0.19），
但反应在隔夜兑现（主口径分数对隔夜收益 t 3.4–3.9），到可交易的次日开盘几乎不剩；等权多空毛夏普 0.3–0.9、扣费后为负。报告以此为核心实证结果。

## 7. 风险、常见坑与应对

最大的两类风险是数据层面的前视偏差和信号太弱导致无结论。前者靠分层对齐、时区校验和时间一致模型控制，后者靠提前的覆盖率统计、合理的预期和预留的降级方案应对。云端作业另有费用、持久化与可用性风险。

| 风险 / 坑 | 影响 | 应对 |
| --- | --- | --- |
| FNSPID 时间戳精度混杂 | 9:00 ET 规则覆盖不全，第一天效应难检验 | 分层对齐；`time_precision` 入表；表 A 按精度子集分栏 |
| FNSPID 时区标注不可信 | 盘后新闻被算进更早的特征日，IC 虚高 | 抽 100 条 URL 抓原页面校验；校验失败的来源降级为仅日期；规则写进 README |
| CSV 列类型不一致、多行字段、俄语记录 | 解析失败或静默错位 | 全字符串读取再转换；正规 CSV 解析器；语言过滤；先用开发样本调通 |
| 正文缺失集中在 Benzinga 行 | 原文与摘要两种文本样本偏小 | 标题用全集；原文与摘要只在正文可用子集上比较，并报告子集规模 |
| LLM 预训练语料含测试期信息 | 嵌入"知道"未来，信号不可信 | ChronoBERT 用按年滚动版本；注明 LLaMA3-8B 知识截止 2023 年 3 月、覆盖测试期，按测试年拆分比较 |
| 摘要引入原文以外的信息 | 摘要输入的结果虚高 | 模块 0 实测 10 条中 3 条加料；放量前改提示词并用 50 条做新旧对比；放量后抽查 100 条并报告比例 |
| 幸存者偏差 | 回测收益高估 | 时点成分股；报告已退市股票的缺失比例 |
| Yahoo 数据质量 | 拆股、异常跳变污染标签 | 异常收益过滤；对权重大的成分股抽查 |
| 新闻覆盖稀疏 | 纯文本模型 IC 接近 0 | 先做覆盖率统计；若稀疏，缩短训练窗口（如 3 年训练 + 1 年验证）或把嵌入前向填充 3–5 日 |
| 信号偏弱 | 结果不显著 | 预期 IC 只有 0.5%–1% 或更低；用多年测试期与 DM 检验，如实报告 |
| PCA / 标准化泄漏 | 测试期指标虚高 | 所有拟合只用训练期；在代码里断言拟合时间段 |
| 信号换手过高 | 扣费后收益为负 | 用 EWCT 控制换手；报告净夏普与成本敏感性 |
| 过拟合调参 | 验证期好、测试期差 | 超参只在验证年上选，测试期只跑一次；多种子报告均值与标准差 |
| Pod 停止后容器盘清空 | 环境、Claude Code 安装、缓存丢失 | 一切持久化到 `/workspace`：双 venv、HF 缓存、vLLM 编译缓存、`~/.claude` 符号链接；每次开机先跑 `bootstrap.sh` |
| SSH 会话读不到模板环境变量与 `RUNPOD_*` 变量 | 路径、线程数、密钥缺失 | 由 `env.sh` 注入；需要 `RUNPOD_*` 时从 `/proc/1/environ` 读取 |
| 库按宿主机 128 核开线程 | 严重超订、反而变慢 | `env.sh` 按 cgroup 配额设置 `NCPU` 与 `OMP_NUM_THREADS` 等；代码并行度取 `$NCPU` |
| shell 启动时往标准输出打印内容 | SFTP、rsync、Desktop SSH 会话失效 | 激活 venv 前设 `VIRTUAL_ENV_DISABLE_PROMPT=1`；`ssh runpod true \| wc -c` 必须为 0 |
| vLLM 的 FlashInfer 采样算子需要 JIT 编译（缺 nvcc） | 引擎初始化失败 | vLLM 脚本在 `import vllm` 之前设 `VLLM_USE_FLASHINFER_SAMPLER=0` |
| 本地上行带宽慢 | Desktop SSH 会话首次部署要等很久，Desktop 更新后可能重来 | 部署结果在卷上可跨 Pod 复用；部署期间可以照常用 Mac 本地会话 + `ssh runpod` 工作 |
| 网络存储卷顺序读带宽有限 | Ridge 阶段被 I/O 拖慢 | 按年把嵌入分片拷到 100GB 容器盘再计算 |
| Claude 账户登录在 Desktop 断开后过期 | 由 Claude 会话维持的长任务中断 | 所有长任务用 `run_bg.sh` 后台运行、分片写入；Claude 只启动和看日志 |
| 两个会话同时改代码 | 冲突或代码分叉 | 同一时间只在一边改；开工先 pull，告一段落就 commit 并 push；Terminate 前确认已 push |
| 机房 L40S 缺货 | 无法开机 | 建卷时选同时有 L40S 与 RTX 6000 Ada 库存的机房；缺货时换 RTX 6000 Ada，其余不变 |
| 云端费用超支 | 预算失控 | 先实测吞吐再放量；不需要数据的工作在 Mac 上做；余额提醒；空闲立即 Terminate Pod |
| Meta 许可审批延迟 | 模块 3 无法开工 | 在模块 0 就提交申请 |
| 新分析依赖全维数据 | 需要重算 | 模块 3 一次算完所有已知标签；卷保留到分析结束 |
| Qlib 版本兼容 | 自定义 Handler 报错 | 固定 Qlib 版本；先用官方 Alpha158 YAML 跑通再改 |
| 规模分组缺历史市值 | 大小盘结论口径不严 | 先用 SEC 历史流通股数估算市值；不行再用 20 日平均成交额代理并注明 |
| 结果为负 | 担心没有可写的成果 | 负结果同样是研究发现：报告差距并分析原因（大盘股、数据覆盖、时间戳精度、文本质量、样本期） |

## 8. 预期产出、验收标准与简历模板

项目完成的标志是：一个可复现的仓库（云端脚本 + 分析脚本 + make 入口）、两张主结果表、核心分析图表，以及至少一个明确的消融结论。

**产出清单**

- [ ] 数据实况表：FNSPID 来源 × 精度 × 正文可用率、各过滤步骤剔除条数、时区校验记录
- [ ] 表 A：文本表示 {LM 词典, TF-IDF, MiniLM, FinBERT, ChronoBERT, LLaMA3-8B} × 文本类型 {标题, 原文, 摘要}，全维 Ridge，日均 IC、等权 / 市值加权五分位多空夏普、DM 检验；按全样本 / 有时刻 / 仅日期三栏
- [ ] 表 B：{Alpha158, 新闻, 融合} × {Ridge, LightGBM, MLP} 的 IC、Rank IC、ICIR、年化超额、信息比率、最大回撤、换手，均值与标准差
- [ ] 成本与换手表：EWCT 不同 ω 下的换手率、毛夏普与净夏普
- [ ] 图 1：含成本的累计多空收益（不同 ω）与 0/5/10/20 bps 敏感性曲线
- [ ] 图 2：规模分组的 IC 与多空收益
- [ ] 表 / 图 3：建仓推迟 k 天（k = 1…5）的多空表现 + IC 衰减曲线（有时刻子集）
- [ ] 图 4：时间一致模型对照（按年滚动 ChronoBERT vs LLaMA3-8B vs FinBERT / MiniLM，按测试年拆分）
- [ ] 文本形式对比表（标题 / 原文 / 摘要）、否定词子样本表、新闻新鲜度对比表
- [ ] 稳健性表：16:00 ET 截止、收盘到收盘成交、十分组、单篇聚合口径
- [ ] README 研究报告与 `make` 入口

**验收标准**

| 项目 | 标准 |
| --- | --- |
| 无前视偏差 | 分层对齐规则与时区校验记录有文档；仅日期记录按 23:59 处理；PCA 只用 2015–2018 拟合；标准化与 λ 只用各窗口的训练期与验证期；测试期只评估一次 |
| 可复现 | 新的 Pod 按 README 从模板部署、跑 `bootstrap.sh` 后，能从卷上的中间产物在一天内重跑出主结果表；云端脚本能从原始数据重跑出中间产物 |
| 有对照 | 文本因子与 Alpha158 的相关性有数字；融合相对基线的提升有均值与标准差 |
| 有稳健性 | 成本与换手、多种子、两种标签口径（开盘到开盘、收盘到收盘）、两种截止口径（9:00、16:00）、两种精度子集 |
| 有诚实的结论 | 明确写出信号在何处失效，以及与原文结果差距的来源 |

**简历条目模板（按实际结果替换 X）**

```markdown
基于 LLM 新闻嵌入的美股截面选股因子研究（复现 Chen, Kelly & Xiu）｜Python, Qlib, PyTorch, vLLM, LightGBM, RunPod
- 基于 Microsoft Qlib 搭建美股研究流水线：S&P 500 时点成分股 2015–2023（约 X 只），自建价格数据并转为 Qlib 格式，复现 Alpha158 + LightGBM 基线
- 处理 FNSPID 约 X 万条新闻，校验时区、按原文规则去重，按时间戳精度分层对齐交易日（9:00 ET 截止 / 次日开盘）；在云端 L40S 上用 LLaMA3-8B 与按年滚动的时间一致模型 ChronoBERT 提取标题、原文、AI 摘要三种文本的嵌入，以充分统计量实现 4096 维年度滚动 Ridge
- 文本因子日均 IC X.XX%，五分位多空等权夏普 X.X（EWCT 换手控制、10 bps 成本后 X.X）；与 Alpha158 融合后 Rank IC 由 X.XX 提升至 X.XX
- 消融：AI 摘要输入相对原文提升 X；推迟一天建仓后夏普衰减 X%；ChronoBERT 与 LLaMA3-8B 差异 X，说明 LLM 前视偏差影响有限/显著
```

写法要点：写清基线与提升幅度、成本假设、一个消融结论。年化收益单独出现没有说服力。

**面试可能追问的问题**

- 为什么用嵌入而不是让模型直接打分？（信息保留 vs prompt 限制，见 2.1）
- 如何保证新闻没有泄漏未来？（时区校验、分层对齐与开盘到开盘标签、仅日期记录按 23:59 处理、按年滚动的 ChronoBERT、摘要抽查）
- 为什么 Ridge 用全维而不是先降维？充分统计量是怎么算的？
- 为什么不做 13B 规模对照？
- 文本因子和量价因子的相关性多高？融合提升是否显著？
- 信号在多少成本下消失？EWCT 如何在换手和收益之间权衡？
- 结果与原文差距的来源是什么？（大盘股、数据覆盖、时间戳精度、文本质量、样本期）
- 为什么把全部计算放在云端一台固定配置的机器上？（避免本地与云端两套环境、数据不用来回搬、GPU 型号按单位工作量成本选）

## 来源

- 论文全文：项目中的 `ssrn-4416687.pdf`（SSRN 4416687 最新版）。第 2 节的设定与数字均出自该文，表号、图号指该版本
- [SSRN 论文页](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416687)、[Dacheng Xiu 主页](https://dachxiu.chicagobooth.edu/)：工作论文状态与获奖信息
- [Bryan Kelly 演讲幻灯片](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2024/09/Kelly-WhartonJL.pdf)、[Sophia Li 讨论幻灯片](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2024/09/ExpectedReturnAndLLM_Discussion_SophiaZhengziLi_NoPause.pdf)：基于较早版本，部分设定已被最新版取代
- [FNSPID 数据卡（Hugging Face）](https://huggingface.co/datasets/Zihan1004/FNSPID)、[FNSPID GitHub](https://github.com/Zdong104/FNSPID_Financial_News_Dataset)、[FNSPID 论文 arXiv 2402.06698](https://arxiv.org/abs/2402.06698)：数据构成、字段、时间戳样本、文件大小与许可
- [Alpaca 历史新闻数据文档](https://docs.alpaca.markets/us/docs/historical-news-data)、[Alpaca News API 参考](https://docs.alpaca.markets/us/reference/news-3)：可扩展新闻源
- [financial-news-multisource（Hugging Face）](https://huggingface.co/datasets/Brianferrell787/financial-news-multisource)、[Drinkall Yahoo Finance 数据集](https://github.com/felixdrinkall/financial-news-dataset)：可扩展新闻源
- [ChronoBERT 模型卡](https://huggingface.co/manelalab/chrono-bert-v1-20181231)、[Chronologically Consistent Large Language Models](https://arxiv.org/abs/2502.21206)：时间一致模型
- [RunPod GPU 定价页](https://www.runpod.io/pricing)、[RunPod Pod 概览](https://docs.runpod.io/pods/overview)、[RunPod：用 VS Code / Cursor 连接 Pod](https://docs.runpod.io/pods/configuration/connect-to-ide)：云端配置、存储语义、SSH 连接
- [Claude Code 桌面应用文档（SSH 会话）](https://code.claude.com/docs/en/desktop)：远程开发工作流
- [OpenAI 批处理 API 文档](https://developers.openai.com/zh-Hans/api/docs/guides/batch)、[ChatGPT 与 API 计费说明](https://help.openai.com/en/articles/8156019-is-api-usage-included-in-chatgpt-subscriptions-even-if-you-have-a-paid-chatgpt-account)：ChatGPT 嵌入可选扩展
- [Qlib Issue #687](https://github.com/microsoft/qlib/issues/687)、[Issue #1953](https://github.com/microsoft/qlib/issues/1953)、[yfinance Issue #2422](https://github.com/ranaroussi/yfinance/issues/2422)：数据获取现状
