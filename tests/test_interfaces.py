"""三个接口文件 + 标准新闻表的 schema 断言。有 dev 样本（Mac 的 dev_data/ 或 Pod 的 /workspace/data/dev_sample/）时对真实样本检查，否则对手写最小表检查。"""
import datetime as dt
from pathlib import Path

import numpy as np
import polars as pl
import pyarrow.parquet as pq
import pytest

from common import ROOT
from news.schema import NEWS_CLEAN, PRED, STANDARD_NEWS, check_schema

SAMPLE_DIRS = [ROOT / "dev_data", Path("/workspace/data/dev_sample")]


def sample_dir() -> Path | None:
    return next((d for d in SAMPLE_DIRS if (d / "embed_candidates_sample.parquet").exists()), None)


def test_standard_news_schema_minimal():
    df = pl.DataFrame({"news_id": ["a"], "ticker": ["AAPL"], "ts_utc": [dt.datetime(2020, 1, 2)], "has_time": [False], "title": ["t"], "body": [None],
                       "has_body": [False], "url": ["https://x"], "source": ["nasdaq.com"], "dataset": ["fnspid"], "source_file": ["nasdaq"]},
                      schema_overrides={"body": pl.Utf8})
    check_schema(df, STANDARD_NEWS, "standard_news")
    with pytest.raises(AssertionError):
        check_schema(df.drop("url"), STANDARD_NEWS, "standard_news")


def test_embedding_shard_schema():
    """接口文件 2：news_id + fixed_size_list<float16, H>。"""
    emb = np.zeros((3, 8), dtype=np.float16)
    import pyarrow as pa
    t = pa.table({"news_id": pa.array(["a", "b", "c"]), "emb": pa.FixedSizeListArray.from_arrays(pa.array(emb.reshape(-1)), 8)})
    assert t.schema.field("emb").type == pa.list_(pa.float16(), 8) and t.schema.field("news_id").type == pa.string()


def test_pred_schema_minimal():
    df = pl.DataFrame({"datetime": [dt.date(2020, 1, 2)], "instrument": ["AAPL"], "score": [0.1]})
    check_schema(df, PRED, "pred")


@pytest.mark.skipif(sample_dir() is None, reason="no dev sample")
def test_dev_sample_matches_interfaces():
    d = sample_dir()
    cand = pl.read_parquet(d / "embed_candidates_sample.parquet")
    check_schema(cand, STANDARD_NEWS, "embed_candidates_sample")
    if (d / "news_clean_sample.parquet").exists():
        check_schema(pl.read_parquet(d / "news_clean_sample.parquet"), NEWS_CLEAN, "news_clean_sample")
    for tt in ("title", "body"):
        f = d / "emb" / "llama3_base" / tt / "part-00000.parquet"
        s = pq.read_schema(f)
        assert str(s.field("emb").type).startswith("fixed_size_list<element: halffloat>[4096]") and str(s.field("news_id").type) == "string"
