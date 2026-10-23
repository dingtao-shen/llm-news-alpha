"""新闻源适配器：每个源一个模块，唯一职责是产出标准新闻表（news/schema.py STANDARD_NEWS，写到 paths.news.embed_candidates）。

- fnspid.py：FNSPID 原始 CSV → parquet（news/parse_fnspid.py）→ 低成本规则过滤 → 标准新闻表（news/candidates.py）。
- 以后新增源（如 alpaca.py）：实现 `build(paths) -> Path`，产出同一张表（news_id 用 news/news_id.py 的定义，ticker 用 news/ticker_map.py 映射，
  ts_utc 为 UTC 瞬时、无时刻的记录给当日 00:00 并 has_time=False，url / source / dataset 填好），
  然后设 DATASET=<name>，依次 make embed / embed-small（或 delta-embed）、news-clean、downstream。
下游（嵌入、对齐、过滤、聚合、Ridge、回测）不读任何源特定的东西。
"""
