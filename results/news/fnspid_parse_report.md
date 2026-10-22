# FNSPID 解析与来源统计

- 总行数 28,606,816；唯一 news_id 12,731,932；日期解析失败 3；有时刻 17,229,919（60.2%）；有正文 4,988,405（17.4%）
- 时间范围 1914-09-16 00:00:00 至 2024-01-09 00:00:00；两文件共有的 news_id 11,551,494

| source_file | 行数 | 唯一 news_id | 时刻可用率 | 正文可用率 | 拒绝行 | symbol_ok | url_http | date_parse | 耗时 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all_external | 13,057,515 | 11,551,495 | 65.9% | 9.6% | 0 | 100.0000% | 99.9941% | 100.0000% | 14.2 |
| nasdaq | 15,549,301 | 12,731,931 | 55.5% | 24.1% | 7 | 100.0000% | 99.9951% | 100.0000% | 30.4 |

## 各文件行数最多的域名

| source_file | url_host | 行数 | 时刻可用率 | 正文可用率 | symbol 为空 |
| --- | --- | ---: | ---: | ---: | ---: |
| all_external | reuters.com | 8,556,310 | 99.9% | 0.0% | 100.0% |
| all_external | benzinga.com | 1,529,287 | 3.7% | 0.0% | 0.0% |
| all_external | seekingalpha.com | 897,219 | 0.0% | 0.0% | 0.0% |
| all_external | lenta.ru | 800,975 | 0.0% | 100.0% | 100.0% |
| all_external | bloomberg.com | 446,578 | 0.0% | 100.0% | 100.0% |
| all_external | zacks.com | 429,559 | 0.0% | 0.0% | 0.0% |
| all_external | gurufocus.com | 193,664 | 0.0% | 0.0% | 0.0% |
| all_external | news.investors.com | 67,555 | 0.0% | 0.0% | 0.0% |
| all_external | investors.com | 62,721 | 0.0% | 0.0% | 0.0% |
| all_external | tradershuddle.com | 16,476 | 0.0% | 0.0% | 0.0% |
| nasdaq | reuters.com | 8,556,310 | 99.9% | 0.0% | 100.0% |
| nasdaq | nasdaq.com | 2,491,785 | 1.1% | 100.0% | 0.0% |
| nasdaq | benzinga.com | 1,529,287 | 3.7% | 0.0% | 0.0% |
| nasdaq | seekingalpha.com | 897,219 | 0.0% | 0.0% | 0.0% |
| nasdaq | lenta.ru | 800,975 | 0.0% | 100.0% | 100.0% |
| nasdaq | bloomberg.com | 446,578 | 0.0% | 100.0% | 100.0% |
| nasdaq | zacks.com | 429,559 | 0.0% | 0.0% | 0.0% |
| nasdaq | gurufocus.com | 193,664 | 0.0% | 0.0% | 0.0% |
| nasdaq | news.investors.com | 67,555 | 0.0% | 0.0% | 0.0% |
| nasdaq | investors.com | 62,721 | 0.0% | 0.0% | 0.0% |

## 带 ticker 的行（能用于个股预测的部分）

| source_file | 带 ticker | 其中有时刻 | 其中有正文 | 其中 2015 年起 |
| --- | ---: | ---: | ---: | ---: |
| all_external | 3,252,888 | 55,987 (1.7%) | 1 (0.0%) | 2,278,101 |
| nasdaq | 5,744,674 | 82,610 (1.4%) | 2,491,780 (43.4%) | 4,549,903 |

明细见 `fnspid_source_stats.csv`（source × host × year）与 `fnspid_source_stats_by_year.csv`。
news_id 定义见 `news/news_id.py`。
