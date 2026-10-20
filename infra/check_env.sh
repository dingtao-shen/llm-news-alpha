#!/usr/bin/env bash
# 环境体检：配额、GPU、两个 venv 的 import 耗时（网络卷上的包 import 可能偏慢）。
set -uo pipefail

echo "== quota"
echo "NCPU=${NCPU:-unset}  OMP_NUM_THREADS=${OMP_NUM_THREADS:-unset}"
if   [ -r /sys/fs/cgroup/memory.max ];                  then m=$(cat /sys/fs/cgroup/memory.max)
elif [ -r /sys/fs/cgroup/memory/memory.limit_in_bytes ]; then m=$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes)
else m=""; fi
[ -n "$m" ] && [ "$m" != max ] && awk -v b="$m" 'BEGIN{printf "memory limit: %.0f GB\n", b/1e9}'

echo "== gpu"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

echo "== import timing"
t() {  # $1 python, $2 label, $3 code
  local s e
  s=$(date +%s.%N)
  if "$1" -c "$3" >/dev/null 2>&1; then ok=ok; else ok=FAIL; fi
  e=$(date +%s.%N)
  awk -v a="$s" -v b="$e" -v l="$2" -v o="$ok" 'BEGIN{printf "%-10s %-4s %5.1fs\n", l, o, b-a}'
}
t /workspace/venv-main/bin/python venv-main "import torch, transformers, polars, duckdb, lightgbm, sklearn, qlib"
t /workspace/venv-vllm/bin/python venv-vllm "import vllm"
echo "(超过 15s 就考虑把 venv 打包后每次解压到容器盘)"

echo "== volume"
du -sh /workspace/hf_cache /workspace/venv-main /workspace/venv-vllm 2>/dev/null
echo "(卷的配额用量以 RunPod 控制台 Storage 页为准，df 显示的是整个存储集群)"
