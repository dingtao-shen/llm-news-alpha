#!/usr/bin/env bash
# llm-news-alpha · RunPod bootstrap
#
# 第一次（卷上还没有仓库时），在 Mac 的仓库根目录执行：
#     ssh runpod 'bash -s' < infra/bootstrap.sh
# 以后每次新开 Pod、连接 Claude Desktop 之前执行：
#     ssh runpod 'bash /workspace/bootstrap.sh'
#
# 幂等：可以反复运行，只做缺失或过期的部分。
# 前提：/workspace/.secrets/env 已有 HF_TOKEN、GH_TOKEN、GIT_NAME、GIT_EMAIL。
#
# 整个脚本包在 main() 里：通过 `bash -s` 从 stdin 读脚本时，bash 会先读完整个函数再执行，
# 中途 apt / pip 读 stdin 不会吞掉脚本的剩余部分。

main() {
set -euo pipefail
W=/workspace
REPO_URL=https://github.com/dingtao-shen/llm-news-alpha.git
REPO=$W/repo
log() { printf '\n[bootstrap] %s\n' "$*"; }

# ---------------------------------------------------------------- 目录与密钥
mkdir -p "$W"/{.claude,hf_cache,.pip_cache,logs,data,qlib_data,mlruns,src,.secrets}
chmod 700 "$W/.secrets"
if [ ! -f "$W/.secrets/env" ]; then
  echo "missing $W/.secrets/env (needs HF_TOKEN, GH_TOKEN, GIT_NAME, GIT_EMAIL)"; exit 1
fi
set -a; . "$W/.secrets/env"; set +a
: "${HF_TOKEN:?HF_TOKEN missing in .secrets/env}"
: "${GH_TOKEN:?GH_TOKEN missing in .secrets/env}"
: "${GIT_NAME:?GIT_NAME missing in .secrets/env}"
: "${GIT_EMAIL:?GIT_EMAIL missing in .secrets/env}"

# ---------------------------------------------------------------- git
log "git identity and credentials"
git config --global user.name "$GIT_NAME"
git config --global user.email "$GIT_EMAIL"
git config --global init.defaultBranch main
git config --global pull.rebase true
# 推送时从环境变量读取 GH_TOKEN；token 本身不写进任何 git 配置文件
git config --global credential.https://github.com.helper \
  '!f() { if [ "$1" = get ]; then echo username=x-access-token; echo "password=$GH_TOKEN"; fi; }; f'

# ---------------------------------------------------------------- 仓库
log "repository"
if [ -d "$REPO/.git" ]; then
  git -C "$REPO" pull --ff-only || echo "WARN: git pull failed (local changes?); continuing with local copy"
else
  git clone "$REPO_URL" "$REPO"
fi

# ---------------------------------------------------------------- env.sh 与启动器
log "env.sh and launcher"
install -m 644 "$REPO/infra/env.sh" "$W/env.sh"
install -m 755 "$REPO/infra/bootstrap.sh" "$W/bootstrap.sh"
touch ~/.bashrc
# 放在 .bashrc 第一行：Ubuntu 的 .bashrc 对非交互 shell 会提前 return，写在末尾不生效
grep -q 'workspace/env.sh' ~/.bashrc || sed -i '1i [ -f /workspace/env.sh ] && . /workspace/env.sh' ~/.bashrc

# ---------------------------------------------------------------- Claude Code 持久化
log "Claude Code config on the volume"
[ -L ~/.claude ] || { rm -rf ~/.claude; ln -s "$W/.claude" ~/.claude; }
[ -f "$W/.claude.json" ] || echo '{}' > "$W/.claude.json"
[ -L ~/.claude.json ] || { rm -f ~/.claude.json; ln -s "$W/.claude.json" ~/.claude.json; }

# ---------------------------------------------------------------- 系统工具（容器盘，每个新 Pod 重装，约 10 秒）
log "system tools"
pkgs=""
command -v tmux  >/dev/null || pkgs="$pkgs tmux"
command -v rsync >/dev/null || pkgs="$pkgs rsync"
command -v gh    >/dev/null || pkgs="$pkgs gh"
command -v gcc   >/dev/null || pkgs="$pkgs build-essential"
if [ -n "$pkgs" ]; then
  { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $pkgs; } </dev/null \
    || echo "WARN: apt-get install failed for:$pkgs"
fi

# ---------------------------------------------------------------- 虚拟环境
# venv-main 复用镜像自带的 torch（在容器盘上，import 快，不占卷），其余依赖装在卷上。
# 用 constraints 锁住 torch，防止 pip 往卷上再装一份 torch。
SYS_TORCH=$(python3 -c "import torch; print(torch.__version__)" 2>/dev/null || true)
CONS=$W/.torch_constraint.txt
if [ -n "$SYS_TORCH" ]; then echo "torch==$SYS_TORCH" > "$CONS"; else : > "$CONS"; fi

stamp_install() {  # $1 venv dir, $2 requirements file, $3 optional constraints file
  local v=$1 req=$2 cons=${3:-} h
  h=$(cat "$req" ${cons:+"$cons"} | sha256sum | cut -c1-16)
  if [ "$(cat "$v/.req_hash" 2>/dev/null)" != "$h" ]; then
    "$v/bin/pip" install -q --upgrade pip </dev/null
    "$v/bin/pip" install -q ${cons:+-c "$cons"} -r "$req" </dev/null
    echo "$h" > "$v/.req_hash"
  else
    echo "  $(basename "$v"): requirements unchanged"
  fi
}

log "venv-main (image torch $SYS_TORCH + project deps)"
[ -x "$W/venv-main/bin/python" ] || python3 -m venv --system-site-packages "$W/venv-main"
stamp_install "$W/venv-main" "$REPO/requirements-main.txt" "$CONS"

log "Qlib (source install, latest release tag at first install)"
if ! "$W/venv-main/bin/python" -c "import qlib" 2>/dev/null; then
  if [ ! -d "$W/src/qlib/.git" ]; then
    tag=$(git ls-remote --tags --refs --sort=-v:refname https://github.com/microsoft/qlib.git 'v*' \
          | head -1 | sed 's#.*refs/tags/##')
    echo "  cloning microsoft/qlib $tag"
    git clone --depth 1 --branch "$tag" https://github.com/microsoft/qlib.git "$W/src/qlib"
  fi
  "$W/venv-main/bin/pip" install -q -c "$CONS" -e "$W/src/qlib" </dev/null
else
  echo "  qlib already installed"
fi

log "venv-vllm (isolated; vLLM pins its own torch)"
[ -x "$W/venv-vllm/bin/python" ] || python3 -m venv "$W/venv-vllm"
stamp_install "$W/venv-vllm" "$REPO/requirements-vllm.txt"

# ---------------------------------------------------------------- 汇总
log "summary"
set +u; . "$W/env.sh"; set -u
"$W/venv-main/bin/python" - <<'PY'
import os, torch, qlib
print(f"  NCPU={os.environ.get('NCPU')}  torch={torch.__version__}  cuda={torch.cuda.is_available()}  "
      f"gpu={torch.cuda.get_device_name(0) if torch.cuda.is_available() else '-'}  qlib={qlib.__version__}")
PY
"$W/venv-vllm/bin/python" -c "import vllm, torch; print(f'  vllm={vllm.__version__}  torch(vllm)={torch.__version__}')" \
  || echo "  WARN: vllm import failed"
echo
echo "bootstrap ok"
}

main "$@"
