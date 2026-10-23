#!/usr/bin/env bash
# 阶段 B 收尾：摘要（第三种文本）→ 4 个模型嵌入 → 聚合 → 滚动 Ridge → 表 A 补"摘要"列。
# 前提：summaries_dir/llama3_instruct/part-*.parquet 全部写完（text/summarize_vllm.py）。已有产物自动跳过。
# 用法：bash infra/run_bg.sh summary-downstream bash models/run_summary.sh
set -uo pipefail
cd /workspace/repo
PY=/workspace/venv-main/bin/python
EMB="$PY -m text.embed --text-type summary"
SMALL="--batch-tokens 131072 --max-batch 2048"
echo "== embed summaries $(date -u +%H:%M:%S)"
$EMB --model llama3_base
$EMB --model finbert $SMALL
$EMB --model minilm  $SMALL
for v in 20191231:2015:2020 20201231:2016:2021 20211231:2017:2022 20221231:2018:2023; do
  IFS=: read -r ver y0 y1 <<< "$v"
  $EMB --model chronobert --version "$ver" --years "$y0" "$y1" $SMALL
done
run() {  # run <model> [test year]
  local model=$1; shift
  local key="${model}__summary__main"
  if [ -f "results/ridge/${key}.json" ]; then echo "skip ${key}: done"; return; fi
  echo "== ${key} $(date -u +%H:%M:%S)"
  [ -f "/workspace/data/fnspid/agg/${model}/summary/main/_meta.json" ] || $PY -m models.aggregate --model "$model" --text-type summary --cutoff main | tail -n 3
  $PY -m models.ridge_suffstats --model "$model" --text-type summary --cutoff main ${1:+--test-years "$@"} | grep -E "^test|^- 全测试期"
}
run llama3_base; run finbert; run minilm
for v in 20191231:2020 20201231:2021 20211231:2022 20221231:2023; do run "chronobert-${v%%:*}" "${v##*:}"; done
$PY -m analysis.table_a
$PY -m analysis.longshort --variants ew
echo "summary-downstream done $(date -u +%H:%M:%S)"
