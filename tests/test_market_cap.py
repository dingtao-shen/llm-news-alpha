import pandas as pd

from data.market_cap import daily_market_cap, shares_records, shares_today_basis


def test_shares_records_and_split_basis():
    facts = {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        {"end": "2019-12-31", "filed": "2020-01-30", "val": 4000},
        {"end": "2019-12-31", "filed": "2020-02-15", "val": 4001},      # 同一 end 的后续重复 → 取最早 filed
        {"end": "2020-09-30", "filed": "2020-10-30", "val": 16000},
    ]}}}}}
    rec = shares_records(facts)
    assert rec["val"].tolist() == [4000, 16000]
    splits = pd.DataFrame({"date": [pd.Timestamp("2020-08-31")], "yf": ["X"], "ratio": [4.0]})
    rec = shares_today_basis(rec, splits)
    assert rec["val_today"].tolist() == [16000.0, 16000.0]              # 拆股前的披露换算到今日口径


def test_daily_market_cap_asof_filed():
    px = pd.DataFrame({"date": pd.to_datetime(["2020-01-29", "2020-01-30", "2020-02-03"]), "close": [10.0, 10.0, 20.0], "volume": [1, 1, 1]})
    rec = pd.DataFrame({"end": pd.to_datetime(["2019-12-31"]), "filed": pd.to_datetime(["2020-01-30"]), "val": [100], "val_today": [100.0]})
    d = daily_market_cap(px, rec)
    assert pd.isna(d.loc[0, "mcap"]) and d.loc[1, "mcap"] == 1000.0 and d.loc[2, "mcap"] == 2000.0   # filed 当天起生效
