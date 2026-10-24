#!/usr/bin/env bash
# 模块 8 备份：把删卷后无法从代码重建、或重建代价高的小产物打成 tgz 放到 /workspace/backup/，
# 给了 rclone remote（如 r2:llm-news-alpha）就再 rclone copy 上去。全维嵌入（15 GB）与聚合（14 GB）不备份：由脚本可重算。
# 用法：bash infra/backup.sh [remote:bucket]
set -euo pipefail
cd /workspace/repo
REMOTE=${1:-}
DS=$(/workspace/venv-main/bin/python -c "from common import load_paths; print(load_paths()['dataset'])")
STAMP=$(date -u +%Y%m%d)
OUT=/workspace/backup; mkdir -p "$OUT"
D=/workspace/data/$DS
tar czf "$OUT/${DS}_small_${STAMP}.tgz" \
  -C /workspace/data "$DS/summaries" "$DS/preds" "$DS/pca" \
  $(cd /workspace/data && find "$DS/agg" -name "_meta.json" | sort) \
  $(cd /workspace/data && ls -d labels market_cap 2>/dev/null) \
  $(cd /workspace/data && ls "$DS/news"/*.json "$DS/news"/*_meta* 2>/dev/null | sort -u)
tar czf "$OUT/news_clean_${DS}_${STAMP}.tgz" -C /workspace/data "$DS/news/news_clean.parquet" "$DS/news/embed_candidates.parquet"
cp -f /workspace/data/dev_sample.tgz "$OUT/dev_sample_${STAMP}.tgz" 2>/dev/null || true
ls -la "$OUT"
sha256sum "$OUT"/*_${STAMP}.tgz > "$OUT/SHA256SUMS_${STAMP}.txt"
if [ -n "$REMOTE" ]; then
  rclone copy "$OUT" "$REMOTE/llm-news-alpha-backup/" --progress
  echo "copied to $REMOTE/llm-news-alpha-backup/"
else
  echo "no remote given: archives are on the network volume only (set BACKUP_REMOTE=<rclone remote:bucket> to upload)"
fi
