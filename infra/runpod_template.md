# RunPod 固定配置

| 项目 | 值 |
| --- | --- |
| 机房 | US-IL-1 |
| 网络存储卷 | `llm-news-vol`，250 GB，Standard，挂载到 `/workspace` |
| 自定义模板 | `llm-news-l40s` |
| 容器镜像 | 官方 Runpod PyTorch（CUDA 12.x）镜像 |
| 容器盘 | 100 GB |
| Volume Disk | 0（由网络卷替代） |
| 端口 | HTTP 8888（JupyterLab），TCP 22（SSH） |
| 模板环境变量 | `HF_HOME=/workspace/hf_cache`，`PIP_CACHE_DIR=/workspace/.pip_cache`（SSH 会话读不到，实际由 `env.sh` 注入） |
| GPU | 1 × L40S 48GB，Secure Cloud，On-Demand |
| 备选 GPU | RTX 6000 Ada 48GB（同机房、同模板，只换 GPU） |

实测（2026-10-21，一台 US-IL-1 的 L40S）：GPU 显存 46068 MiB；cgroup v1 CPU 配额 17.85 核；
内存上限约 125 GB。不同宿主机的配额不同，代码按 94 GB 内存预算，线程数由 `env.sh` 自动读取。

## 每次开工

1. 控制台 Pods → Deploy：先选网络卷 `llm-news-vol` → GPU 选 L40S → 模板 `llm-news-l40s` → Deploy On-Demand。
2. Connect → "SSH over exposed TCP"，把 IP 与端口填进 Mac `~/.ssh/config` 的 `Host runpod`。
3. `ssh runpod 'bash /workspace/bootstrap.sh'`（必须在连接 Claude Desktop 之前）。
4. Claude Desktop → Code → 环境选 SSH `runpod` → 项目文件夹 `/workspace/repo`。

Desktop SSH 会话第一次连接时，要从 Mac 上传助手程序，本地上行网速慢时可能要等很久。
部署结果保存在 `/workspace/.claude/remote`，换 Pod 后可以复用；但 Desktop 更新后可能需要重新部署。

## 收工

Terminate Pod（不要 Stop）。网络卷上的数据、venv、模型权重都保留。

## 卷上的固定位置

| 路径 | 内容 |
| --- | --- |
| `/workspace/repo` | 本仓库 |
| `/workspace/env.sh`、`/workspace/bootstrap.sh` | 由 bootstrap 从仓库安装 |
| `/workspace/.secrets/env` | `HF_TOKEN`、`GH_TOKEN`、`GIT_NAME`、`GIT_EMAIL`（权限 600，永不进 git） |
| `/workspace/venv-main`、`/workspace/venv-vllm` | 两个虚拟环境 |
| `/workspace/src/qlib` | Qlib 源码（editable 安装） |
| `/workspace/hf_cache` | Hugging Face 模型缓存 |
| `/workspace/data`、`/workspace/qlib_data`、`/workspace/mlruns`、`/workspace/logs` | 数据、Qlib 二进制、MLflow、日志 |
| `/workspace/.claude`、`/workspace/.claude.json` | Claude Code 远程安装与配置（`~` 下是指向这里的符号链接） |
