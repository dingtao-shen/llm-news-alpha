# llm-news-alpha · 每个 shell 启动时最先执行（由 bootstrap.sh 安装到 /workspace/env.sh，
# 并插到 ~/.bashrc 第一行）。交互式 shell、ssh 远程命令、Claude Code 都会读到。
# 激活 venv 时不改 PS1：否则 .bashrc 的交互判断失效，非交互 shell 会打印横幅并破坏 sftp
export VIRTUAL_ENV_DISABLE_PROMPT=1
export HF_HOME=/workspace/hf_cache
export PIP_CACHE_DIR=/workspace/.pip_cache
export PYTHONPATH=/workspace/repo
export MLFLOW_TRACKING_URI=file:/workspace/mlruns
export HF_HUB_DISABLE_TELEMETRY=1

# 线程数 = cgroup CPU 硬限制（向下取整）；读不到时用 RUNPOD_CPU_COUNT，最后才用 nproc。
# 不设的话 torch / polars / LightGBM / BLAS 会按宿主机的 128 核开线程，严重超订。
NCPU=""
if [ -r /sys/fs/cgroup/cpu.max ]; then                       # cgroup v2
  read _q _p < /sys/fs/cgroup/cpu.max; [ "$_q" != max ] && NCPU=$(( _q / _p ))
elif [ -r /sys/fs/cgroup/cpu/cpu.cfs_quota_us ]; then        # cgroup v1
  _q=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us); _p=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us)
  [ "$_q" -gt 0 ] && NCPU=$(( _q / _p ))
fi
[ -z "$NCPU" ] && NCPU=$(tr '\0' '\n' < /proc/1/environ 2>/dev/null | sed -n 's/^RUNPOD_CPU_COUNT=//p')
[ -z "$NCPU" ] && NCPU=$(nproc)
export NCPU OMP_NUM_THREADS=$NCPU MKL_NUM_THREADS=$NCPU OPENBLAS_NUM_THREADS=$NCPU \
       NUMEXPR_MAX_THREADS=$NCPU POLARS_MAX_THREADS=$NCPU RAYON_NUM_THREADS=$NCPU
unset _q _p

[ -f /workspace/.secrets/env ] && { set -a; . /workspace/.secrets/env; set +a; }
[ -f /workspace/venv-main/bin/activate ] && . /workspace/venv-main/bin/activate
