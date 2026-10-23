# Qlib 数据集校验（/workspace/qlib_data/us_sp500，2026-10-23）

- `dump_bin.py dump_all`：632 个 CSV（631 只成分股 + SPY），字段 open/high/low/close/volume/factor/adj_close，9 秒。
- 日历 2,433 个交易日（2014-06-02 至 2024-01-30），与 SPY 交易日完全一致 → `news_clean.parquet` 用 SPY 日历对齐的特征日无需重算。
- `instruments/sp500.txt` 时点成员数：2015-01-02 499、2019-06-28 505、2023-12-29 503，与成分股表一致；`BRK.B`、`FB`、`META` 都能取到数据。
- 标签表达式 `Ref($open,-2)/Ref($open,-1)-1` 可直接计算。
- 价格来源：yfinance 552 只（Close 已按拆股调整，factor 只含分红）+ FNSPID `full_history.zip` 79 只（只取成分股窗口内的行，拼接断点前的段丢弃）。
- 成分股区间内 2015–2023 的股票-日 1,141,896 个，有价格 1,063,905 个（**93.2%**）；按年：2015 85.2%、2016 89.0%、2017 91.6%、2018 93.3%、2019 96.2%、2020 95.1%、2021 93.7%、2022 96.1%、2023 98.3%。
  缺口全部来自 85 只 Yahoo 与 FNSPID 都没有的退市公司（AET、APC、BRCM、CA、CELG、ESRX、MON、RTN、UTX、TWX 等）以及 FNSPID 旧抓取止于 2020-07 的部分区间。
- 质量：|日收益| > 50% 的记录 28 条，抽查均为真实事件（GME 2021-01、FOSL、FLR 2020-03、APA 2020-03-09）；成交量为 0 的股票-日 1,627 个。
- 遗留：早年退市公司缺价格会使 2015–2017 年的股票池偏向幸存者；可考虑的补充来源：Stooq、Kaggle 含退市股的历史数据集、付费的 EODHD / Tiingo。
