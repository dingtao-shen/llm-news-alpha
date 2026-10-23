from news.filters import body_length_ok, bow, cosine, near_duplicates, near_duplicates_by_group


def test_body_length():
    assert body_length_ok(None)                       # 只有标题不适用
    assert not body_length_ok("short body")
    assert body_length_ok("x" * 100) and body_length_ok("x" * 100_000) and not body_length_ok("x" * 100_001)


def test_cosine():
    a, b = bow("Apple beats estimates on strong iPhone sales"), bow("Apple beats estimates on strong iPhone sales!")
    assert abs(cosine(a, b) - 1.0) < 1e-9
    assert cosine(bow("apple apple"), bow("banana")) == 0.0


def test_near_duplicates_window_and_order():
    base = "Exxon accelerates production in Guyana, makes two new discoveries offshore in the Stabroek block"
    rows = [
        ("a", 0, base),
        ("b", 2, base + " (update)"),                    # 2 个交易日后几乎相同 → 重复
        ("c", 6, base),                                  # 距 a 6 天 > 5，但距 b … b 没被保留，所以不算 → 保留
        ("d", 7, "Chevron reports quarterly loss on weak refining margins"),
        ("e", 7, "Chevron posts quarterly loss as refining margins weaken sharply"),   # 与 d 词重叠不足 0.8 → 保留
    ]
    assert near_duplicates(rows) == ["b"]
    # 窗口内与被保留的 c（第 6 天）相同 → 重复
    assert near_duplicates(rows + [("f", 11, base)]) == ["b", "f"]
    # 顺序无关：输入乱序结果相同
    assert near_duplicates(list(reversed(rows))) == ["b"]


def test_by_group_serial_equals_parallel():
    g = {"X": [("a", 0, "same text here again"), ("b", 1, "same text here again")],
         "Y": [("c", 0, "same text here again"), ("d", 9, "same text here again")]}   # 不同股票互不比较；Y 内相隔 9 天
    assert near_duplicates_by_group(g, workers=1) == {"b"}
    assert near_duplicates_by_group(g, workers=2) == {"b"}
