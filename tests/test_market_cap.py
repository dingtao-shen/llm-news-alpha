import pandas as pd

from data.market_cap import daily_market_cap, drop_scale_errors, shares_records, shares_today_basis


def test_shares_records_and_split_basis():
    facts = {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        {"end": "2019-12-31", "filed": "2020-01-30", "val": 4000},
        {"end": "2019-12-31", "filed": "2020-02-15", "val": 4001},      # 同一 end 的后续重复 → 取最早 filed
        {"end": "2020-09-30", "filed": "2020-10-30", "val": 16000},
        {"end": "2021-03-31", "filed": "2021-04-30", "val": 16000000},  # 按千股填报的量级错误 → 剔除
        {"end": "2021-06-30", "filed": "2021-07-30", "val": 12000},     # 两个股票类别同一文件分别披露 → 求和
        {"end": "2021-06-30", "filed": "2021-07-30", "val": 4000},
    ]}}}}}
    rec, element = shares_records(facts)
    assert element == "dei:EntityCommonStockSharesOutstanding"
    assert rec["val"].tolist() == [4000, 16000, 16000000, 16000]
    splits = pd.DataFrame({"date": [pd.Timestamp("2020-08-31")], "yf": ["X"], "ratio": [4.0]})
    rec = drop_scale_errors(shares_today_basis(rec, splits))
    assert rec["val_today"].tolist() == [16000.0, 16000.0, 16000.0]     # 拆股前的披露换算到今日口径；量级错误在换算后剔除


def test_fallback_to_consolidated_element():
    facts = {"facts": {"dei": {}, "us-gaap": {"CommonStockSharesOutstanding": {"units": {"shares": [
        {"end": f"20{y}-12-31", "filed": f"20{y + 1}-02-01", "val": 100 + y, "form": "10-K"} for y in range(15, 21)]}}}}}
    rec, element = shares_records(facts)
    assert element == "us-gaap:CommonStockSharesOutstanding" and len(rec) == 6


def test_daily_market_cap_asof_filed():
    px = pd.DataFrame({"date": pd.to_datetime(["2020-01-29", "2020-01-30", "2020-02-03"]), "close": [10.0, 10.0, 20.0], "volume": [1, 1, 1]})
    rec = pd.DataFrame({"end": pd.to_datetime(["2019-12-31"]), "filed": pd.to_datetime(["2020-01-30"]), "val": [100], "val_today": [100.0]})
    d = daily_market_cap(px, rec)
    assert pd.isna(d.loc[0, "mcap"]) and d.loc[1, "mcap"] == 1000.0 and d.loc[2, "mcap"] == 2000.0   # filed 当天起生效
