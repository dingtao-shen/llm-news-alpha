"""跨模块共用的小工具：仓库根目录、paths.yaml、线程数。"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _resolve(obj: Any, dataset: str) -> Any:
    if isinstance(obj, dict):
        return {k: _resolve(v, dataset) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve(v, dataset) for v in obj]
    if isinstance(obj, str):
        return obj.replace("{dataset}", dataset)
    return obj


@lru_cache(maxsize=None)
def load_paths() -> dict[str, Any]:
    """读取仓库根目录的 paths.yaml；所有数据路径只从这里来。
    路径里的 `{dataset}` 用环境变量 DATASET（默认 paths.yaml 的 dataset 字段）替换：换新闻源时下游产物各自一套目录。"""
    with open(ROOT / "paths.yaml", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    dataset = os.environ.get("DATASET", cfg.get("dataset", "fnspid"))
    cfg = _resolve(cfg, dataset)
    cfg["dataset"] = dataset
    return cfg


def ncpu() -> int:
    """并行度：env.sh 按 cgroup 配额算出的 NCPU；读不到时退回 4（不要用 os.cpu_count()）。"""
    return int(os.environ.get("NCPU", "4"))
