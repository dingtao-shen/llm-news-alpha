#!/usr/bin/env bash
# λ 口径敏感性：所有 模型×文本 用固定相对 λ 重跑滚动 Ridge（聚合复用），输出键带 __lam<值> 后缀，不覆盖验证选 λ 的结果。
# 用法：bash infra/run_bg.sh lambda-sens bash models/run_lambda_sensitivity.sh 10
set -uo pipefail
cd /workspace/repo
LAM=${1:-10}
PY=/workspace/venv-main/bin/python
run() { local model=$1 text=$2; shift 2
  [ -f "results/ridge/${model}__${text}__main__lam${LAM}.json" ] && { echo "skip ${model}__${text}"; return; }
  $PY -m models.ridge_suffstats --model "$model" --text-type "$text" --cutoff main --lambda-rel "$LAM" ${1:+--test-years "$@"} | grep -E "^test"; }
for text in title body; do
  run llama3_base $text; run finbert $text; run minilm $text
  for v in 20191231:2020 20201231:2021 20211231:2022 20221231:2023; do run "chronobert-${v%%:*}" $text "${v##*:}"; done
done
echo "lambda-sens done"
