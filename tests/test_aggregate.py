import datetime as dt

import numpy as np
import polars as pl

from models.aggregate import group_mean


def test_group_mean_counts_and_flags():
    emb = np.array([[1, 1], [3, 3], [10, 10], [5, 5], [7, 7]], dtype=np.float16)
    rows = np.array([0, 1, 2, 3, 4])
    keys = pl.DataFrame({
        "datetime": [dt.date(2020, 1, 3), dt.date(2020, 1, 2), dt.date(2020, 1, 2), dt.date(2020, 1, 2), dt.date(2020, 1, 3)],
        "instrument": ["AAPL", "AAPL", "MSFT", "AAPL", "AAPL"],
        "is_timed": [False, True, False, False, False], "has_body": [True, False, True, True, False], "in_sp500": [True, True, False, True, True]})
    g, mean = group_mean(emb, rows, keys)
    assert g["datetime"].to_list() == [dt.date(2020, 1, 2), dt.date(2020, 1, 2), dt.date(2020, 1, 3)]
    assert g["instrument"].to_list() == ["AAPL", "MSFT", "AAPL"]
    assert g["news_cnt"].to_list() == [2, 1, 2] and g["n_timed"].to_list() == [1, 0, 0] and g["n_body"].to_list() == [1, 1, 1]
    assert g["in_sp500"].to_list() == [True, False, True]
    assert np.allclose(mean.astype(np.float32), [[4, 4], [10, 10], [4, 4]])
