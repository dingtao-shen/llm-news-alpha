"""news_id 的 Python 与 SQL 实现一致；DuckDB 解析迷你 CSV（多行正文、"" 引号、俄语行、00:00:00 行、同一新闻多 ticker）。"""
import duckdb
import pytest

from news.news_id import news_id, norm_title, norm_url
from news.parse_fnspid import NEWS_ID_SQL, read_csv_sql, select_sql

CSV = '''Unnamed: 0,Date,Article_title,Stock_symbol,Url,Publisher,Author,Article,Lsa_summary,Luhn_summary,Textrank_summary,Lexrank_summary
0.0,2023-12-16 23:00:00 UTC,Interesting A Put And Call Options,A,https://www.nasdaq.com/articles/interesting-a-put?x=1,,,"Line one, with comma.
Line two has a ""quoted"" word.",,,,
1.0,2020-05-22 00:00:00 UTC,30 Stocks Moving in Friday's Pre-Market Session,A,https://www.benzinga.com/news/20/05/16092879/30-stocks,Lisa Levin,,,,,,
2.0,2020-05-22 00:00:00 UTC,  30 Stocks Moving in Friday's  Pre-Market Session ,AAPL,http://benzinga.com/news/20/05/16092879/30-stocks/#top,Lisa Levin,,,,,,
3.0,2019-01-05,Газпром отчитался о прибыли,GAZP,https://lenta.ru/news/2019/01/05/gazprom/,Lenta,,,,,,
4.0,not a date,Broken row,MSFT,ftp://x,,,,,,,
'''

CASES = [
    ("https://www.nasdaq.com/articles/foo?x=1#frag", "  Hello   World "),
    ("HTTP://Nasdaq.com/articles/foo/", "hello world"),
    ("", ""), (None, None),
    ("https://lenta.ru/news/2019/01/05/gazprom/", "Газпром отчитался о прибыли"),
    ("https://x.com/a b", "Tab\there\nnewline"),
]


def test_norm():
    assert norm_url("https://www.nasdaq.com/articles/foo?x=1#frag") == "nasdaq.com/articles/foo"
    assert norm_url("HTTP://Nasdaq.com/articles/foo/") == "nasdaq.com/articles/foo"
    assert norm_title("  Hello   World ") == "hello world"
    assert news_id(CASES[0][0], CASES[0][1]) == news_id(CASES[1][0], CASES[1][1])
    assert len(news_id("a", "b")) == 24 and news_id(None, None) == news_id("", "")


def test_sql_matches_python():
    con = duckdb.connect()
    rows = [(u, t, news_id(u, t)) for u, t in CASES]
    con.execute("CREATE TABLE t(Url VARCHAR, Article_title VARCHAR, expected VARCHAR)")
    con.executemany("INSERT INTO t VALUES (?, ?, ?)", rows)
    got = con.execute(f"SELECT {NEWS_ID_SQL}, expected FROM t").fetchall()
    assert all(a == b for a, b in got), got


def test_parse_mini_csv(tmp_path):
    p = tmp_path / "mini.csv"
    p.write_text(CSV, encoding="utf-8")
    con = duckdb.connect()
    df = con.execute(select_sql(read_csv_sql(str(p)), "nasdaq") + " ORDER BY Stock_symbol, Article_title").df()
    assert len(df) == 5
    assert con.execute("SELECT count(*) FROM reject_errors").fetchone()[0] == 0
    r = df.set_index("Stock_symbol")
    body = r.loc["A"]["Article"].dropna().iloc[0]
    assert body == 'Line one, with comma.\nLine two has a "quoted" word.'
    a = df[df.Stock_symbol == "A"].sort_values("Date")
    assert list(a.has_time) == [False, True] and list(a.has_body) == [False, True]
    assert str(a.ts_utc.iloc[1]) == "2023-12-16 23:00:00"
    # 同一篇新闻（URL 带 www/#top，标题多余空白）在 A 与 AAPL 下 news_id 相同
    ids = df[df.Article_title.str.contains("Pre-Market")].news_id.unique()
    assert len(ids) == 1 and ids[0] == news_id("https://www.benzinga.com/news/20/05/16092879/30-stocks", "30 Stocks Moving in Friday's Pre-Market Session")
    assert r.loc["GAZP"]["url_host"] == "lenta.ru" and str(r.loc["GAZP"]["ts_utc"]) == "2019-01-05 00:00:00"
    assert r.loc["MSFT"]["ts_utc"] is None or str(r.loc["MSFT"]["ts_utc"]) == "NaT"
    assert r.loc["MSFT"]["url_host"] == ""
    assert (df.source_file == "nasdaq").all()
