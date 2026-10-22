"""news/candidates.py：每条规则各剔除哪些行、去重保留带正文的行、输出按 news_id 排序且唯一。"""
import duckdb
import polars as pl
import pytest

from news.candidates import build_candidates, load_universe
from news.news_id import news_id
from news.parse_fnspid import read_csv_sql, select_sql

ROWS = [
    # Date, title, symbol, url, article
    ("2015-03-02 00:00:00 UTC", "Apple beats estimates", "AAPL", "https://www.nasdaq.com/articles/apple-beats", "Apple reported strong results."),
    ("2015-03-02 00:00:00 UTC", "Apple beats estimates", "AAPL", "https://nasdaq.com/articles/apple-beats/", ""),          # 同 news_id 无正文 → 去重时丢弃
    ("2014-12-30 00:00:00 UTC", "Too early", "AAPL", "https://www.benzinga.com/x/1", ""),                                   # 日期早于 2014-12-31
    ("2014-12-31 00:00:00 UTC", "On the margin day", "MSFT", "https://www.benzinga.com/x/2", ""),                           # 刚好在余量日 → 保留
    ("2016-01-05 00:00:00 UTC", "Газпром отчитался", "GAZP", "https://lenta.ru/news/1", "текст"),                            # 俄语
    ("2016-01-05 00:00:00 UTC", "   ", "MSFT", "https://www.benzinga.com/x/3", ""),                                        # 空标题
    ("2016-01-05 07:30:00 UTC", "Small cap news", "ZZZZ", "https://www.benzinga.com/x/4", ""),                             # 不在成分股全集
    ("2016-01-06 00:00:00 UTC", "10 Biggest Movers", "AAPL", "https://www.benzinga.com/x/5", ""),                           # 多 ticker 同一篇
    ("2016-01-06 00:00:00 UTC", "10 Biggest Movers", "MSFT", "https://www.benzinga.com/x/5", ""),
    ("2016-01-06 00:00:00 UTC", "10 Biggest Movers", "ZZZZ", "https://www.benzinga.com/x/5", ""),
    ("2017-05-01 09:15:00 UTC", "Berkshire annual meeting", "BRK-B", "https://www.benzinga.com/x/6", ""),                   # '-' 与 '.' 等价
    ("not a date", "Broken", "AAPL", "https://www.benzinga.com/x/7", ""),
]


def _csv(rows):
    def q(x):
        return '"' + x.replace('"', '""') + '"'
    head = "Unnamed: 0,Date,Article_title,Stock_symbol,Url,Publisher,Author,Article,Lsa_summary,Luhn_summary,Textrank_summary,Lexrank_summary\n"
    return head + "".join(f"{i}.0,{d},{q(t)},{s},{u},,,{q(a)},,,,\n" for i, (d, t, s, u, a) in enumerate(rows))


def test_build_candidates(tmp_path):
    csv = tmp_path / "mini.csv"; csv.write_text(_csv(ROWS), encoding="utf-8")
    pq = tmp_path / "pq"; pq.mkdir()
    con = duckdb.connect()
    con.execute(f"COPY ({select_sql(read_csv_sql(str(csv)), 'nasdaq')}) TO '{pq / 'data_0.parquet'}' (FORMAT parquet)")
    uni_file = tmp_path / "u.txt"; uni_file.write_text("AAPL\nMSFT\nBRK.B\nGOOG\n")
    universe = load_universe(uni_file)
    assert universe == {"AAPL": "AAPL", "MSFT": "MSFT", "BRK.B": "BRK.B", "GOOG": "GOOG"}

    out = tmp_path / "cand.parquet"
    stats = build_candidates(con, f"{pq}/*.parquet", universe, out)
    f = stats["funnel"]
    assert f["raw_rows"] == 12
    assert f["after_date"] == 10          # 剔除 2014-12-30 与坏日期
    assert f["after_lang"] == 9           # 剔除俄语
    assert f["after_title"] == 8          # 剔除空标题
    assert f["after_ticker"] == 6         # 剔除 ZZZZ ×2（单条 + 榜单里的一行）
    assert f["after_single"] == 4         # 榜单文章剩下的 AAPL、MSFT 两行整篇剔除
    assert stats["single_stock_removed_total"] == {"rows": 2, "articles": 1}
    assert stats["dedup_removed"] == 1 and stats["n_candidates"] == 3 and stats["n_with_body"] == 1
    assert stats["unmatched_tickers_top20"] == [{"symbol": "ZZZZ", "rows": 2}]

    df = pl.read_parquet(out)
    assert df.columns == ["news_id", "ticker", "ts_utc", "has_time", "title", "body", "has_body", "source_file"]
    assert df["news_id"].is_sorted() and df["news_id"].n_unique() == 3
    r = df.filter(pl.col("ticker") == "AAPL").row(0, named=True)
    assert r["news_id"] == news_id("https://www.nasdaq.com/articles/apple-beats", "Apple beats estimates")
    assert r["body"] == "Apple reported strong results." and r["has_body"] and not r["has_time"]
    assert set(df["ticker"]) == {"AAPL", "MSFT", "BRK.B"}       # BRK-B 映射回成分股表写法
    assert df.filter(pl.col("ticker") == "BRK.B")["has_time"][0] is True
    assert df.filter(pl.col("ticker") == "MSFT")["body"][0] is None
