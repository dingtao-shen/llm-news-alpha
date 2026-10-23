"""FNSPID 源适配器：把两步（解析 + 候选集）串成"产出标准新闻表"这一个动作。实际逻辑在 news/parse_fnspid.py 与 news/candidates.py。

运行：python -m news.sources.fnspid  （等价于 make news-parse（若 parquet 不存在）+ make news-candidates）
"""
from __future__ import annotations

from pathlib import Path

from common import load_paths


def build(paths: dict | None = None) -> Path:
    paths = paths or load_paths()
    pq_dir = Path(paths["news"]["parquet_dir"])
    if not (pq_dir / "nasdaq" / "_SUCCESS").exists():
        from news.parse_fnspid import main as parse_main
        parse_main()
    from news.candidates import main as cand_main
    cand_main()
    return Path(paths["news"]["embed_candidates"])


if __name__ == "__main__":
    print(build())
