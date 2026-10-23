# 近似历史市值覆盖

- 有价格的股票 631 只：有 CIK 555，有股数披露 553，有市值的股票-日 90.0%（其余用 adv20 代理）
- 拆股事件 609 个（yfinance），用于把披露股数换算到今日口径
- 输出 `/workspace/data/market_cap/market_cap.parquet`

| 年 | 股票-日 | 有市值 | 比例 |
| --- | ---: | ---: | ---: |
| 2014 | 80,641 | 72,458 | 89.9% |
| 2015 | 144,910 | 124,448 | 85.9% |
| 2016 | 146,776 | 126,548 | 86.2% |
| 2017 | 147,081 | 127,666 | 86.8% |
| 2018 | 148,134 | 129,399 | 87.4% |
| 2019 | 150,010 | 132,171 | 88.1% |
| 2020 | 146,341 | 134,201 | 91.7% |
| 2021 | 142,702 | 134,684 | 94.4% |
| 2022 | 142,501 | 134,965 | 94.7% |
| 2023 | 142,963 | 135,543 | 94.8% |
| 2024 | 11,040 | 10,860 | 98.4% |

股数来源元素分布：{"dei:EntityCommonStockSharesOutstanding": 516, "none": 78, "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding": 28, "us-gaap:CommonStockSharesOutstanding": 8, "us-gaap:WeightedAverageNumberOfSharesOutstandingBasic": 1}

缺市值的股票（无 CIK，多为退市公司）：ABC, ABMD, ADS, AGN, ALXN, ANSS, ARNC, ATVI, AVB, BBBY, BLL, CDAY, CERN, CHK, CMA, COG, CTL, CTLT, CTRA, CTXS, CXO, DFS, DISCA, DISCK, DISH, DNR, DO, DRE, EA, EMC, ENDP, EQR, ETFC, FI, FL, FLIR, FLT, FRC, FTR, GPS, HBI, HES, HFC, HOLX, INFO, IPG, JNPR, JWN, K, KSU, LEG, LM, MNK, MRO, MXIM, MYL, NBL, NLOK, PBCT, PDCO, PEAK, PXD, QEP, QRVO, RE, SRCL, SWN, TGNA, TIF, TWTR, VAR, WBA, WRK, WYND, XEC, XLNX

有 CIK 但没有可用股数披露：STZ, V
