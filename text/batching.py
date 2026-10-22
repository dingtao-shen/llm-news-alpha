"""分片与分批的纯函数（不依赖 torch，Mac 上可测）。"""
from __future__ import annotations


def make_batches(lengths: list[int], batch_tokens: int, max_batch: int) -> list[list[int]]:
    """按长度降序排列后贪心成批：批内 padding 到最长，满足 len(batch) * max_len <= batch_tokens 且 len(batch) <= max_batch。
    返回每批的原始行号列表；所有行号恰好出现一次。"""
    assert batch_tokens > 0 and max_batch > 0
    order = sorted(range(len(lengths)), key=lambda i: -lengths[i])
    batches: list[list[int]] = []
    cur: list[int] = []
    cur_max = 0
    for i in order:
        L = max(lengths[i], 1)
        new_max = max(cur_max, L)  # 降序，所以 new_max == cur_max 除第一条
        if cur and ((len(cur) + 1) * new_max > batch_tokens or len(cur) + 1 > max_batch):
            batches.append(cur)
            cur, cur_max = [], 0
            new_max = L
        cur.append(i)
        cur_max = new_max
    if cur:
        batches.append(cur)
    return batches


def shard_name(i: int) -> str:
    return f"part-{i:05d}.parquet"


def padded_tokens(lengths: list[int], batches: list[list[int]]) -> int:
    return sum(len(b) * max(lengths[i] for i in b) for b in batches)
