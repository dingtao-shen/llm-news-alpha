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
