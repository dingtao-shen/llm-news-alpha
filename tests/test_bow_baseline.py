import polars as pl

from text.bow_baseline import lm_polarity, news_text


def test_lm_polarity_counts():
    pos, neg = {"GAIN", "STRONG"}, {"LOSS", "WEAK", "DECLINE"}
    assert lm_polarity("Strong gain offsets a weak loss, loss again", pos, neg) == (2, 3, 8)
    assert lm_polarity("", pos, neg) == (0, 0, 0)


def test_news_text_variants():
    df = pl.DataFrame({"title": ["T"], "body": ["b" * 10000]})
    assert news_text(df, "title").to_list() == ["T"]
    assert len(news_text(df, "body")[0]) == 2 + 8000
