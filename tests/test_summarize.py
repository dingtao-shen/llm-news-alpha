from text.summarize_vllm import clean_summary, extra_content_hints, make_conv


def test_clean_summary():
    assert clean_summary("Acme beat estimates.", "t") == ("Acme beat estimates.", "ok")
    assert clean_summary("Here is a 2-3 sentence summary of the article about Acme:\n\nAcme beat estimates.", "t") == ("Acme beat estimates.", "stripped_preamble")
    assert clean_summary("No summary is needed as the article does not mention AMD.", "AMD headline") == ("AMD headline", "fallback_title")
    assert clean_summary("There is no specific article about Disney (DIS) in the text.", "Disney vs Roku") == ("Disney vs Roku", "fallback_title")
    assert clean_summary("Here is a summary of the article:", "Netflix Stock Opportunity") == ("Netflix Stock Opportunity", "fallback_title")


def test_hints_and_conv():
    h = extra_content_hints("Acme rose 12% to $8.1 billion; CEO Jane left.", "Acme rose 12% to $8.1 billion.")
    assert h["new_numbers"] == [] and "Jane" in h["new_names"] and not h["omission_phrase"]
    conv = make_conv("SYS", "AAPL", "Apple beats", "body text")
    assert conv[0]["role"] == "system" and conv[1]["content"].startswith("Ticker: AAPL\nHeadline: Apple beats")


def test_shard_ok_rejects_dead_engine_output():
    from text.summarize_vllm import shard_ok
    assert shard_ok([40, 55, 0, 61] + [50] * 96)            # 1% 空输出：正常
    assert not shard_ok([0] * 950 + [45] * 50)               # 95% 空输出：引擎已挂
    assert shard_ok([])


def test_clean_summary_catches_not_mentioned_refusals():
    assert clean_summary("Caterpillar (CAT) is not mentioned in the article. The article discusses GM and NVDA.", "3 Stocks to Trade") == ("3 Stocks to Trade", "fallback_title")
    assert clean_summary("This article does not mention Coca-Cola (KO) or any other specific company.", "Investing 101") == ("Investing 101", "fallback_title")
    assert clean_summary("GOOG is mentioned as a company, but it is not the main subject of the article. The article discusses TTD.", "TTD earnings") == ("TTD earnings", "fallback_title")
    # 正文里说 "not mentioned" 的真实摘要不算拒答：只看首句
    s = "Acme (ACME) raised guidance to $2.10. The dividend was not mentioned."
    assert clean_summary(s, "t") == (s, "ok")
