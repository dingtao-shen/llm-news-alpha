#!/usr/bin/env bash
# 用 Qlib TopkDropout 多头回测外部 Ridge 预测（接口文件 3）；每个 key 一个 MLflow 实验 external_<key>，报告写 results/baseline/。
# 用法：bash infra/run_bg.sh ext-bt bash models/run_external_backtests.sh llama3_base__body__main chronobert__body__main
set -uo pipefail
cd /workspace/repo
PY=/workspace/venv-main/bin/python
PRED=$($PY -c "from common import load_paths; print(load_paths()['pred_dir'])")
for key in "$@"; do
  echo "== $key $(date -u +%H:%M:%S)"
  PRED_PATH="$PRED/$key.parquet" EXP_NAME="external_$key" /workspace/venv-main/bin/qrun configs/external_ridge.yaml 2>&1 | grep -E "^\{|'IC'|'Rank IC'|annualized_return|information_ratio|max_drawdown|Traceback|ERROR" | head -20
  $PY -m analysis.baseline_report --exp "external_$key" 2>&1 | grep -E "^- 信号|^\| excess_return_with_cost/(annualized_return|information_ratio|max_drawdown)|^\| 20" | head -8
done
echo "ext-bt done"
