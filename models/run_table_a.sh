#!/usr/bin/env bash
# 表 A 初表：对每个 模型 × 文本类型 跑 聚合 → 滚动 Ridge（主口径）。已有结果的组合跳过（看 results/ridge/<key>.json）。
# 用法：bash infra/run_bg.sh table-a bash models/run_table_a.sh
set -uo pipefail
cd /workspace/repo
PY=/workspace/venv-main/bin/python
run() {  # run <model> <text_type> [test years...]
  local model=$1 text=$2; shift 2
  local key="${model}__${text}__main"
  if [ -f "results/ridge/${key}.json" ]; then echo "skip ${key}: done"; return; fi
  echo "== ${key} $(date -u +%H:%M:%S)"
  [ -f "/workspace/data/agg/${model}/${text}/main/_meta.json" ] || $PY -m models.aggregate --model "$model" --text-type "$text" --cutoff main | tail -n 3
  $PY -m models.ridge_suffstats --model "$model" --text-type "$text" --cutoff main ${1:+--test-years "$@"} | grep -E "^test|^- 全测试期"
}
run llama3_base body
run finbert title;  run finbert body
run minilm  title;  run minilm  body
for v in 20191231:2020 20201231:2021 20211231:2022 20221231:2023; do
  run "chronobert-${v%%:*}" title "${v##*:}"
  run "chronobert-${v%%:*}" body  "${v##*:}"
done
$PY -m analysis.table_a
echo "table-a done $(date -u +%H:%M:%S)"
