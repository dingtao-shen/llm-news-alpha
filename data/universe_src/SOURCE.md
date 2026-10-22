# S&P 500 时点成分股源数据

- 来源：<https://github.com/shardul0701/SP500-Survivorship-bias-data-2004-2026>，
  目录 `src/sp500_ticker_history/`，commit `40a9ddc31bb421b93186e321333d05c07e5d1dd3`（2026-10-21）。
- 原始数据出自 [fja05680/sp500](https://github.com/fja05680/sp500)（MIT License），2019 年后的变更按 S&P Global 官方公告核对。
- 只拷贝了本项目需要的 2015–2023 年 9 个文件，内容未改动。提交进仓库是为了构建与测试不依赖网络。
- 格式：`tickers_on_Jan_1`（上一年最后交易日的成员）与 `changes`（`difference` 移出、`union` 加入）。
- 已知口径：GOOG/GOOGL 为两只股票；FB→META 记为 2022-06-09 同日移出/加入；`BRK.B`、`BF.B` 保持点号记法。
