"""模块 2 任务 6（对齐原文）：正文长度过滤、同一股票 5 个交易日内的词袋近似重复过滤。

- 长度：有正文的记录正文字符数不在 [MIN_CHARS, MAX_CHARS] 内的剔除；只有标题的记录不适用。
- 近似重复：按股票分组、按时间排序；每条记录的词袋（标题 + 正文，小写 [a-z0-9]+ 词频）与同一股票在前 WINDOW 个交易日内
  （含当日）已保留记录的余弦相似度 >= THRESHOLD 时剔除本条（保留更早的那条）。交易日用特征日的日历下标衡量。
  纯 Python 词典点积，按股票并行（NCPU 进程）。
"""
from __future__ import annotations

import math
import multiprocessing
import re
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor

MIN_CHARS, MAX_CHARS = 100, 100_000
THRESHOLD, WINDOW = 0.8, 5
_TOKEN = re.compile(r"[a-z0-9]+")


def body_length_ok(body: str | None) -> bool:
    if body is None:
        return True
    n = len(body.strip())
    return MIN_CHARS <= n <= MAX_CHARS


def bow(text: str) -> tuple[dict[str, int], float]:
    c = Counter(_TOKEN.findall(text.lower()))
    return dict(c), math.sqrt(sum(v * v for v in c.values())) or 1.0


def cosine(a: tuple[dict, float], b: tuple[dict, float]) -> float:
    da, na = a
    db, nb = b
    if len(da) > len(db):
        da, db = db, da
    return sum(v * db[k] for k, v in da.items() if k in db) / (na * nb)


def near_duplicates(rows: list[tuple[str, int, str]], threshold: float = THRESHOLD, window: int = WINDOW) -> list[str]:
    """rows: (news_id, day_index, text)，同一股票；返回被判为重复、应剔除的 news_id 列表。
    处理顺序按 (day_index, news_id)，保证确定性。"""
    rows = sorted(rows, key=lambda r: (r[1], r[0]))
    kept: deque[tuple[int, tuple[dict, float]]] = deque()
    dup: list[str] = []
    for news_id, day, text in rows:
        while kept and kept[0][0] < day - window:
            kept.popleft()
        v = bow(text)
        if any(cosine(v, kv) >= threshold for _, kv in kept):
            dup.append(news_id)
        else:
            kept.append((day, v))
    return dup


def near_duplicates_by_group(groups: dict[str, list[tuple[str, int, str]]], workers: int,
                             threshold: float = THRESHOLD, window: int = WINDOW) -> set[str]:
    """按股票并行。groups: ticker -> rows。"""
    big = sorted(groups.values(), key=len, reverse=True)   # 大组先派发，负载更均匀
    if workers <= 1 or len(big) < 2:
        return {d for g in big for d in near_duplicates(g, threshold, window)}
    out: set[str] = set()
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as ex:
        for dups in ex.map(near_duplicates, big, [threshold] * len(big), [window] * len(big), chunksize=4):
            out.update(dups)
    return out
