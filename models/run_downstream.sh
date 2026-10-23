#!/usr/bin/env bash
# 从 news_clean 重跑全部下游：聚合 → 滚动 Ridge（全部模型×文本，含 ChronoBERT 四版）→ 表 A → 多空 → DM → 信号拆分 → λ 敏感性。
# 会删除并重建当前数据集的 agg/、preds/ 与 results/ridge、results/longshort。换数据源后（DATASET=<name>）同样一条命令。
# 用法：bash infra/run_bg.sh downstream bash models/run_downstream.sh
set -uo pipefail
cd /workspace/repo
PY=/workspace/venv-main/bin/python
AGG=$($PY -c "from common import load_paths; print(load_paths()['agg_dir'])")
PRED=$($PY -c "from common import load_paths; print(load_paths()['pred_dir'])")
echo "== clean $AGG $PRED results/ridge results/longshort $(date -u +%H:%M:%S)"
rm -rf "$AGG" "$PRED" results/ridge results/longshort; mkdir -p "$AGG" "$PRED" results/ridge results/longshort
[ -f "$($PY -c "from common import load_paths; print(load_paths()['labels'])")" ] || $PY -m models.labels | tail -n 1
bash models/run_table_a.sh                      # 聚合 + Ridge（含 llama3 标题）+ 表 A
$PY -m analysis.table_a | head -3
$PY -m analysis.longshort | grep -E "^\| LLaMA3-8B / 标题|^\| ChronoBERT.*原文" | head -2
$PY -m analysis.dm_test | grep -E "显著优于"
$PY -m analysis.signal_decomposition | grep -E "^## |overnight|main_oo" | head -12
bash models/run_lambda_sensitivity.sh 10 | tail -n 1
$PY -m analysis.lambda_sensitivity --lam 10 | tail -n 2
echo "downstream done $(date -u +%H:%M:%S)"
