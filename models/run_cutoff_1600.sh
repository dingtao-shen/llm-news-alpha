#!/usr/bin/env bash
# 16:00 ET 稳健性口径：对全部 模型×文本 做 cutoff=1600 的聚合 + 滚动 Ridge（CPU；嵌入复用）。
# 用法：bash infra/run_bg.sh cutoff1600 bash models/run_cutoff_1600.sh
set -uo pipefail
cd /workspace/repo
PY=/workspace/venv-main/bin/python
AGG=$($PY -c "from common import load_paths; print(load_paths()['agg_dir'])")
run() { local model=$1 text=$2; shift 2
  [ -f "results/ridge/${model}__${text}__1600.json" ] && { echo "skip ${model}__${text}__1600"; return; }
  [ -f "$AGG/$model/$text/1600/_meta.json" ] || $PY -m models.aggregate --model "$model" --text-type "$text" --cutoff 1600 | tail -n 2
  $PY -m models.ridge_suffstats --model "$model" --text-type "$text" --cutoff 1600 ${1:+--test-years "$@"} | grep -E "^test"; }
for text in title body; do
  run llama3_base $text; run finbert $text; run minilm $text
  for v in 20191231:2020 20201231:2021 20211231:2022 20221231:2023; do run "chronobert-${v%%:*}" $text "${v##*:}"; done
done
echo "cutoff1600 done $(date -u +%H:%M:%S)"
