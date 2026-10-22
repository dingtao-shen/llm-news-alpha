# Worklog

新条目写在最上面。每条：做了什么 / 产出在哪 / 下一步 / 遗留问题。

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
