"""news_id 的定义（固定，以后不再改动）。SQL 版在 news/parse_fnspid.py 的 NEWS_ID_SQL，两者由测试互相校验。

    norm_url   = lower(去首尾 ASCII 空白(Url))，去掉开头的 http:// 或 https://、去掉开头的 www.、
                 去掉第一个 '#' 或 '?' 及其后内容、去掉结尾的 '/'
    norm_title = lower(去首尾 ASCII 空白(Article_title))，连续 ASCII 空白折叠为一个空格
    news_id    = sha256(norm_url + "\\n" + norm_title) 的十六进制前 24 位（96 bit）

URL 或标题为空（NULL）按空串参与。同一篇新闻出现在多个 ticker 下得到同一个 news_id，
这是单一股票规则与去重的前提。ASCII 空白指 [ \\t\\r\\n\\f\\v]，与 DuckDB 的 RE2 正则保持一致。
"""
from __future__ import annotations

import hashlib
import re

_WS = r"[ \t\r\n\f\v]"
_STRIP = re.compile(rf"^{_WS}+|{_WS}+$")
_COLLAPSE = re.compile(rf"{_WS}+")


def _strip(s: str) -> str:
    return _STRIP.sub("", s)


def norm_url(url: str | None) -> str:
    u = _strip(url or "").lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = re.sub(r"[#?].*$", "", u)
    return re.sub(r"/+$", "", u)


def norm_title(title: str | None) -> str:
    return _COLLAPSE.sub(" ", _strip(title or "").lower())


def news_id(url: str | None, title: str | None) -> str:
    key = norm_url(url) + "\n" + norm_title(title)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
