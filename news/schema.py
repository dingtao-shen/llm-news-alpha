"""接口文件 0：标准新闻表（embed_candidates.parquet）。任何新闻源的解析器都产出这张表，之后的 嵌入 / 对齐 / 过滤 / 聚合 只认它。

列（按 news_id 排序，行组 = 嵌入分片大小 5 万）：
  news_id         str   sha256(norm_url + "\\n" + norm_title)[:24]，见 news/news_id.py
  ticker          str   成分股表写法（BRK.B）
  ts_utc          datetime  数据源给的时间（有时刻的为 UTC 瞬时；仅日期的为该日 00:00 占位）
  has_time        bool  是否有时刻
  title, body     str   body 为空表示只有标题
  has_body        bool
  url             str   原文链接（日期修正、来源拆分用）
  source          str   发布方域名（benzinga.com / nasdaq.com / …）
  dataset         str   数据集名（fnspid / alpaca / …）
  source_file     str   数据集内的文件（可选，FNSPID 为 nasdaq / all_external）
"""
import polars as pl

STANDARD_NEWS = {"news_id": pl.Utf8, "ticker": pl.Utf8, "ts_utc": pl.Datetime("us"), "has_time": pl.Boolean, "title": pl.Utf8,
                 "body": pl.Utf8, "has_body": pl.Boolean, "url": pl.Utf8, "source": pl.Utf8, "dataset": pl.Utf8, "source_file": pl.Utf8}

NEWS_CLEAN = {"news_id": pl.Utf8, "ticker": pl.Utf8, "ts_et": pl.Datetime("us"), "time_precision": pl.Utf8, "title": pl.Utf8, "body": pl.Utf8,
              "has_body": pl.Boolean, "body_chars": pl.Int32, "url": pl.Utf8, "source": pl.Utf8, "dataset": pl.Utf8, "source_file": pl.Utf8,
              "date_fix": pl.Utf8, "feature_day": pl.Date, "feature_day_1600": pl.Date, "in_sp500": pl.Boolean}

PRED = {"datetime": pl.Date, "instrument": pl.Utf8, "score": pl.Float64}


def check_schema(df: pl.DataFrame, expected: dict, name: str) -> None:
    """列名与类型必须完全匹配 expected 的前缀顺序（允许额外列在后面）。"""
    cols = list(expected)
    assert df.columns[: len(cols)] == cols, f"{name}: columns {df.columns[: len(cols)]} != {cols}"
    for c, t in expected.items():
        assert df.schema[c] == t, f"{name}: {c} is {df.schema[c]}, expected {t}"
