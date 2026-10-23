from news.ticker_map import map_symbol, normalize_symbol

U = {"AAPL", "BRK.B", "BF.B", "FB", "META"}


def test_normalize_and_alias():
    assert normalize_symbol(" brk-b ") == "BRK.B"
    assert map_symbol("BRK-B", U) == "BRK.B" and map_symbol("BRK.B", U) == "BRK.B"
    assert map_symbol("BRK", U) == "BRK.B"           # FNSPID 的伯克希尔写法
    assert map_symbol("FB", U) == "FB" and map_symbol("META", U) == "META"   # 新旧代码各自保留
    assert map_symbol("ZZZZ", U) is None and map_symbol(None, U) is None
