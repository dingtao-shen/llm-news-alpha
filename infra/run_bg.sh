#!/usr/bin/env bash
# 把长任务彻底脱离 SSH / Claude 会话在后台运行。
# 用法：infra/run_bg.sh <job-name> <command> [args...]
# 输出写到 /workspace/logs/<job-name>_<时间戳>.log；查看进度：tail -f <log>
set -euo pipefail
[ $# -ge 2 ] || { echo "usage: $0 <job-name> <command> [args...]"; exit 2; }
name=$1; shift
log=/workspace/logs/${name}_$(date +%Y%m%d_%H%M%S).log
mkdir -p /workspace/logs
setsid nohup "$@" > "$log" 2>&1 < /dev/null &
echo "started $name  pid=$!  log=$log"
