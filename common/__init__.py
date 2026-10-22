"""跨模块共用的小工具：仓库根目录、paths.yaml、线程数。"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=None)
def load_paths() -> dict[str, Any]:
    """读取仓库根目录的 paths.yaml；所有数据路径只从这里来。"""
    with open(ROOT / "paths.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def ncpu() -> int:
    """并行度：env.sh 按 cgroup 配额算出的 NCPU；读不到时退回 4（不要用 os.cpu_count()）。"""
    return int(os.environ.get("NCPU", "4"))
