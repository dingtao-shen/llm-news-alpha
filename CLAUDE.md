# CLAUDE.md · llm-news-alpha

复现 Chen, Kelly & Xiu《Expected Returns and Large Language Models》：LLM 新闻嵌入 → 年度滚动 Ridge → 次日截面收益预测 → 五分位多空回测，并在 Qlib 中与 Alpha158 做增量检验。
完整计划见 claude.ai 项目文档《Expected Returns and Large Language Models Qlib 复现计划》；本文件只写工作约定。

## 两个环境

| | Mac（本地会话） | RunPod Pod（SSH 会话） |
| --- | --- | --- |
| 用途 | 写代码、重构、用 `dev_data/` 样本跑 pytest、作图、写文档 | 全量数据、GPU、Qlib、训练、回测 |
| 仓库 | 本地克隆 | `/workspace/repo` |
| Python | 轻量 env（`requirements-dev.txt`），没有 torch / Qlib | `venv-main`（默认激活）、`venv-vllm`（只用于 vLLM 摘要） |
| 数据 | 只有 `dev_data/` 小样本 | `/workspace/data` 等，路径一律从 `paths.yaml` 读 |

判断当前环境：`test -d /workspace && echo pod || echo mac`。在 Mac 上不要尝试跑需要 GPU、全量数据或 Qlib 的命令。

代码的唯一真相源是 GitHub 仓库；数据的唯一真相源是网络卷 `/workspace`；Pod 是一次性的。两边会话历史不共享，交接靠 git 提交和 `docs/worklog.md`。

## Pod 上的资源约束

- GPU：L40S，可用显存约 45 GB；LLaMA3-8B bf16 权重约 16 GB。
- CPU：线程数用环境变量 `$NCPU`（由 `/workspace/env.sh` 按 cgroup 配额计算，约 16–17）。不要用 `os.cpu_count()` 或 `nproc`（它们返回宿主机的 128 核）。joblib / LightGBM / DataLoader 的并行度都取 `int(os.environ["NCPU"])`。
- 内存：按 94 GB 预算写代码（不同宿主机配额不同），超出会被直接 OOM kill，没有 Python 报错。大表用 polars lazy / DuckDB 流式处理。
- 网络卷是网络文件系统：适合大文件顺序读写，不适合海量小文件。分片文件保持在 100 MB–2 GB；计算密集的随机读先把分片拷到容器盘（`/root` 或 `/tmp`，100 GB）。

## 必须遵守的规则

1. **长任务（> 5 分钟）一律用 `bash infra/run_bg.sh <job> <cmd...>` 启动**，不要在前台跑，也不要依赖会话保持连接。启动后只用 `tail` 看日志。长任务的脚本必须按 news_id / 年份分片写出，支持断点续跑（已存在的分片跳过）。
2. **删除或覆盖 `/workspace/data`、`/workspace/hf_cache`、`/workspace/qlib_data` 下的任何文件前，先向用户确认。**
3. 大文件不进 git（见 `.gitignore`）。只有 `results/` 下的小表格与图提交。
4. 绝不打印、记录或提交密钥。`/workspace/.secrets/env` 里的 `HF_TOKEN`、`GH_TOKEN` 只通过环境变量使用；检查是否存在用 `test -n "$HF_TOKEN"`，不要 `echo` 它。
5. 新依赖：Pod 上加到 `requirements-main.txt` 或 `requirements-vllm.txt` 后跑 `make bootstrap`，再 `make lock` 并提交 lock 文件；不要临时 `pip install` 了事。不要在 venv-main 里安装或升级 torch。
6. 每次会话结束前，在 `docs/worklog.md` 顶部追加一条：做了什么、产出在哪、下一步、遗留问题。

## 前视偏差红线（改动相关代码时逐条自查）

- 新闻对齐：有时刻的记录用 9:00 ET 截止；只有日期的记录一律视为当日 23:59:59 ET，绝不能视为 00:00。
- 特征日 t 对应标签是 t+1 开盘买入、t+2 开盘卖出（`Ref($open,-2)/Ref($open,-1)-1`）；回测 `deal_price: open`。
- PCA 只在 2015–2018 拟合；标准化统计量只用各滚动窗口的训练期；λ 与超参只在验证年选；测试年只评估一次。
- 时区校验未通过的来源，时刻作废，降级为仅日期。
- 嵌入缓存以 news_id 为键，不以 (ticker, date) 为键。

## 三个接口文件

| 文件 | 键 | 说明 |
| --- | --- | --- |
| `news_clean.parquet` | `news_id` | ticker、美东时间戳、`time_precision`（second/day）、标题、正文、两种口径的特征日 |
| 嵌入分片（`emb_dir/<model>/<text_type>/part-*.parquet` 或 `.npy` + 索引） | `news_id` | float16 |
| `pred.parquet` | `(datetime, instrument)` | `score`；每个 模型 × 文本类型 × 口径 一个文件 |

模块之间只通过这三个文件交互；改它们的 schema 要同步更新本节和所有读写方。

## 代码约定

- Python 3.12，类型注解，函数小而纯；路径从 `paths.yaml` 读。
- 表格处理优先 polars / DuckDB；与 Qlib 交接处用 pandas。
- 解析、过滤、对齐等逻辑必须有 `tests/` 下的 pytest，用 `dev_data/` 样本或手写小例子，Mac 上能跑。
- 随机种子固定并写进输出元数据。
- 提交信息：`<模块>: <做了什么>`，例如 `news: add layered alignment with 23:59 rule for day-precision rows`。

## 常用命令

```bash
make help          # 所有目标
make check-env     # [Pod] 配额、GPU、import 耗时
make smoke         # [Pod] 模块 0 验收
make test          # 单元测试
bash infra/run_bg.sh <job> <cmd...>   # [Pod] 后台长任务
```
