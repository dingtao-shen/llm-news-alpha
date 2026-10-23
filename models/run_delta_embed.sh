#!/usr/bin/env bash
# 增量嵌入：候选集里尚无嵌入的 news_id（例如补了 BRK.B 别名、或换数据源后新来的新闻），对全部模型 × 文本类型追加 delta 分片。
# 用法：bash infra/run_bg.sh delta-embed bash models/run_delta_embed.sh <tag>
set -uo pipefail
cd /workspace/repo
TAG=${1:-$(date +%Y%m%d)}
PY=/workspace/venv-main/bin/python
SMALL="--batch-tokens 131072 --max-batch 2048"
for text in title body; do
  $PY -m text.embed --model llama3_base --text-type $text --delta "$TAG" | grep -E "^inputs|^done|nothing"
  $PY -m text.embed --model finbert --text-type $text --delta "$TAG" $SMALL | grep -E "^inputs|^done|nothing"
  $PY -m text.embed --model minilm  --text-type $text --delta "$TAG" $SMALL | grep -E "^inputs|^done|nothing"
  for v in 20191231:2015:2020 20201231:2016:2021 20211231:2017:2022 20221231:2018:2023; do
    IFS=: read ver y0 y1 <<< "$v"
    $PY -m text.embed --model chronobert --version $ver --years $y0 $y1 --text-type $text --delta "$TAG" $SMALL | grep -E "^inputs|^done|nothing"
  done
done
echo "delta-embed done"
