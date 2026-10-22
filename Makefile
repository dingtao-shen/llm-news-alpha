SHELL := /bin/bash
.DEFAULT_GOAL := help

PY      ?= /workspace/venv-main/bin/python
VLLM_PY ?= /workspace/venv-vllm/bin/python

# 长任务一律用 $(BG) 启动：脱离会话后台运行，日志写到 /workspace/logs/
BG := bash infra/run_bg.sh

.PHONY: help bootstrap check-env verify-llama smoke-embed smoke-vllm smoke lock test universe news-download news-parse news-stats news-candidates

help:  ## 列出所有目标
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-16s %s\n", $$1, $$2}'

# ---------------------------------------------------------------- 模块 0：环境（Pod）
bootstrap:  ## [Pod] 重新执行 bootstrap（拉代码、更新 venv）
	bash /workspace/bootstrap.sh

check-env:  ## [Pod] 配额、GPU、import 耗时体检
	bash infra/check_env.sh

verify-llama:  ## [Pod] 核对卷上 LLaMA 3 权重的 commit 与 SHA-256
	$(PY) infra/verify_llama.py

smoke-embed:  ## [Pod] LLaMA3-8B 10 条文本嵌入 + 吞吐
	$(PY) infra/smoke_embed.py

smoke-vllm:  ## [Pod] LLaMA3-8B-Instruct + vLLM 10 条摘要
	$(VLLM_PY) infra/smoke_vllm.py

smoke: smoke-embed smoke-vllm  ## [Pod] 模块 0 最终验收

lock:  ## [Pod] 把两个 venv 的实际版本写入 *.lock（随后提交）
	/workspace/venv-main/bin/pip freeze --local --exclude-editable > requirements-main.lock
	$(VLLM_PY) -m pip freeze > requirements-vllm.lock
	@echo "wrote requirements-main.lock, requirements-vllm.lock"

# ---------------------------------------------------------------- 通用
test:  ## [Mac/Pod] 单元测试
	python -m pytest -q

# ---------------------------------------------------------------- 模块 1：价格与股票池
universe:  ## [Pod] 时点成分股 → qlib instruments/sp500.txt + results/universe/
	$(PY) -m data.build_universe

# ---------------------------------------------------------------- 模块 2：新闻
news-download:  ## [Pod] 后台下载 FNSPID 两个 CSV 到 /workspace/data/raw/fnspid
	$(BG) fnspid-download $(PY) -m news.download_fnspid

news-parse:  ## [Pod] 后台把 CSV 解析为全字符串 parquet（含 news_id、质量指标）
	$(BG) fnspid-parse $(PY) -m news.parse_fnspid

news-stats:  ## [Pod] 来源 × 年份 × 时刻/正文可用率 → results/news/
	$(PY) -m news.source_stats

news-candidates:  ## [Pod] 后台生成嵌入候选集 embed_candidates.parquet + GPU 时间估算
	$(BG) news-candidates $(PY) -m news.candidates

# ---------------------------------------------------------------- 后续模块（实现时补上）
# 模块 1：prices qlib-dump qlib-baseline market-cap
# 模块 2：news-sample news-tz news-clean
# 模块 3：benchmark embed summarize bow ridge pca
# 模块 4–6：qlib-news qlib-fusion analyze
# 模块 8：backup
