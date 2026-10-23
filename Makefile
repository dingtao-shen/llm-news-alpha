SHELL := /bin/bash
.DEFAULT_GOAL := help

PY      ?= /workspace/venv-main/bin/python
VLLM_PY ?= /workspace/venv-vllm/bin/python

# 长任务一律用 $(BG) 启动：脱离会话后台运行，日志写到 /workspace/logs/
BG := bash infra/run_bg.sh

.PHONY: help bootstrap check-env verify-llama smoke-embed smoke-vllm smoke lock test universe prices prices-fill qlib-dump qlib-baseline news-download news-parse news-stats news-candidates news-clean embed-trial embed embed-small labels aggregate ridge table-a longshort dev-sample

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

dev-sample:  ## [Pod] 生成约 100 MB 开发样本并打包到 /workspace/data/dev_sample.tgz（Mac 的 dev_data/）
	$(PY) infra/make_dev_sample.py

# ---------------------------------------------------------------- 模块 1：价格与股票池
universe:  ## [Pod] 时点成分股 → qlib instruments/sp500.txt + results/universe/
	$(PY) -m data.build_universe

prices:  ## [Pod] 后台 yfinance 下载成分股全集 + SPY 到 /workspace/data/prices，并写覆盖率报告
	$(BG) prices $(PY) -m data.download_prices

prices-fill:  ## [Pod] 用 FNSPID full_history.zip 补 yfinance 缺失的价格（带拼接/代码复用防护）
	$(PY) -m data.fill_prices_fnspid

qlib-dump:  ## [Pod] 价格 CSV → Qlib 二进制（calendars、features、instruments/all.txt；sp500.txt 由 make universe 生成）
	$(PY) /workspace/src/qlib/scripts/dump_bin.py dump_all --data_path /workspace/data/prices --qlib_dir /workspace/qlib_data/us_sp500 \
	  --include_fields open,high,low,close,volume,factor,adj_close --date_field_name date --symbol_field_name symbol --max_workers $$NCPU

qlib-baseline:  ## [Pod] 后台 qrun Alpha158(无 VWAP) + LightGBM 基线，结果在 /workspace/mlruns
	$(BG) qlib-baseline /workspace/venv-main/bin/qrun configs/baseline_alpha158.yaml

# ---------------------------------------------------------------- 模块 2：新闻
news-download:  ## [Pod] 后台下载 FNSPID 两个 CSV 到 /workspace/data/raw/fnspid
	$(BG) fnspid-download $(PY) -m news.download_fnspid

news-parse:  ## [Pod] 后台把 CSV 解析为全字符串 parquet（含 news_id、质量指标）
	$(BG) fnspid-parse $(PY) -m news.parse_fnspid

news-stats:  ## [Pod] 来源 × 年份 × 时刻/正文可用率 → results/news/
	$(PY) -m news.source_stats

news-candidates:  ## [Pod] 后台生成嵌入候选集 embed_candidates.parquet + GPU 时间估算
	$(BG) news-candidates $(PY) -m news.candidates

news-clean:  ## [Pod] 候选集 → news_clean.parquet（对齐、长度、近似重复）+ news_panel.parquet + results/news/ 报告
	$(BG) news-clean $(PY) -m news.build_clean

# ---------------------------------------------------------------- 模块 3：嵌入
MODEL ?= llama3_base
embed-trial:  ## [Pod] 2,000 条试跑（标题 + 原文），输出到 /tmp，打印吞吐、显存与三种读回校验
	$(PY) -m text.embed --model $(MODEL) --text-type title --limit 2000 --shard-size 1000 --out /tmp/embed_trial --verify-readback
	$(PY) -m text.embed --model $(MODEL) --text-type body  --limit 2000 --shard-size 1000 --out /tmp/embed_trial --verify-readback

embed:  ## [Pod] 后台：先标题全集，再原文子集；已完成分片自动跳过
	$(BG) embed-$(MODEL) bash -c '$(PY) -m text.embed --model $(MODEL) --text-type title && $(PY) -m text.embed --model $(MODEL) --text-type body'

# 小模型：FinBERT、MiniLM 全集；ChronoBERT 按年滚动（测试年 Y 用 (Y-1)1231 版本，只嵌入 [Y-5, Y] 窗口）。batch 预算放大，显存仍很小。
SMALL := --batch-tokens 131072 --max-batch 2048
EMB   := $(PY) -m text.embed
embed-small:  ## [Pod] 后台：FinBERT、MiniLM、ChronoBERT ×4 的标题与原文嵌入；已完成分片自动跳过
	$(BG) embed-small bash -c '\
	  $(EMB) --model finbert --text-type title $(SMALL) && $(EMB) --model finbert --text-type body $(SMALL) && \
	  $(EMB) --model minilm  --text-type title $(SMALL) && $(EMB) --model minilm  --text-type body $(SMALL) && \
	  $(EMB) --model chronobert --version 20191231 --years 2015 2020 --text-type title $(SMALL) && $(EMB) --model chronobert --version 20191231 --years 2015 2020 --text-type body $(SMALL) && \
	  $(EMB) --model chronobert --version 20201231 --years 2016 2021 --text-type title $(SMALL) && $(EMB) --model chronobert --version 20201231 --years 2016 2021 --text-type body $(SMALL) && \
	  $(EMB) --model chronobert --version 20211231 --years 2017 2022 --text-type title $(SMALL) && $(EMB) --model chronobert --version 20211231 --years 2017 2022 --text-type body $(SMALL) && \
	  $(EMB) --model chronobert --version 20221231 --years 2018 2023 --text-type title $(SMALL) && $(EMB) --model chronobert --version 20221231 --years 2018 2023 --text-type body $(SMALL)'

# ---------------------------------------------------------------- 模块 3：聚合与 Ridge
TEXT   ?= title
CUTOFF ?= main
labels:  ## [Pod] Qlib 算所有口径的标签 → /workspace/data/labels/labels_sp500.parquet
	$(PY) -m models.labels

aggregate:  ## [Pod] 股票-日聚合嵌入：make aggregate MODEL=llama3_base TEXT=title CUTOFF=main
	$(PY) -m models.aggregate --model $(MODEL) --text-type $(TEXT) --cutoff $(CUTOFF)

ridge:  ## [Pod] 年度滚动充分统计量 Ridge → pred.parquet + results/ridge/：make ridge MODEL=llama3_base TEXT=title CUTOFF=main
	$(BG) ridge-$(MODEL)-$(TEXT)-$(CUTOFF) $(PY) -m models.ridge_suffstats --model $(MODEL) --text-type $(TEXT) --cutoff $(CUTOFF)

table-a:  ## [Pod] 后台：所有 模型 × 文本类型 的聚合 + Ridge，再汇成 results/ridge/table_a.md（已有结果跳过）
	$(BG) table-a bash models/run_table_a.sh

# ---------------------------------------------------------------- 模块 6：回测与分析
longshort:  ## [Pod/Mac] preds 里每个 模型×文本 的五分位多空（等权）、成本、EWCT → results/longshort/
	$(PY) -m analysis.longshort

# ---------------------------------------------------------------- 后续模块（实现时补上）
# 模块 1：market-cap
# 模块 2：news-sample news-tz
# 模块 3：benchmark summarize bow pca
# 模块 4–6：qlib-news qlib-fusion analyze（其余）
# 模块 8：backup
