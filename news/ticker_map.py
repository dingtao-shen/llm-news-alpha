"""模块 2 任务 5：FNSPID 的 Stock_symbol → 成分股表（instruments/sp500.txt）的代码。

- 规范化：去空白、大写、'-' 视为 '.'（FNSPID 与 yfinance 写 BRK-B，成分股表写 BRK.B）。
- 别名：FNSPID 自己的写法 → 成分股表代码（如 BRK → BRK.B：FNSPID 用 BRK 表示伯克希尔，不区分 A/B 股；新闻是公司层面的，归到成分股 BRK.B）。
- 代码变更（FB→META 等）不在这里映射：成分股表把新旧代码当作两个区间，新闻按发布当时的代码归属即可。
- 无法映射到成分股全集的记录由调用方统计（candidates.py 报未匹配前 20）。
"""
from __future__ import annotations

ALIASES: dict[str, str] = {
    "BRK": "BRK.B",
}


def normalize_symbol(sym: str | None) -> str:
    """FNSPID / yfinance 写法 → 成分股表写法（不含别名）。"""
    return (sym or "").strip().upper().replace("-", ".")


def map_symbol(sym: str | None, universe: set[str] | dict[str, str], aliases: dict[str, str] = ALIASES) -> str | None:
    """返回成分股表代码；不在全集中返回 None。universe 的元素是成分股表写法（含点号）。"""
    s = normalize_symbol(sym)
    s = aliases.get(s, s)
    return s if s in universe else None
