from text.batching import make_batches, padded_tokens, shard_name


def test_make_batches_covers_all_once_and_respects_budget():
    lengths = [5, 512, 300, 300, 17, 1, 0, 512, 128, 64] * 7
    batches = make_batches(lengths, batch_tokens=1024, max_batch=8)
    seen = sorted(i for b in batches for i in b)
    assert seen == list(range(len(lengths)))
    for b in batches:
        m = max(max(lengths[i], 1) for i in b)
        assert len(b) * m <= 1024 and len(b) <= 8
    # 降序：第一批都是 512
    assert all(lengths[i] == 512 for i in batches[0]) and len(batches[0]) == 2
    assert padded_tokens(lengths, batches) >= sum(max(x, 1) for x in lengths)


def test_pad_ratio_limits_waste():
    lengths = [80] * 10 + [12] * 990          # 10 条长标题 + 990 条短标题
    batches = make_batches(lengths, batch_tokens=200_000, max_batch=1024, max_pad_ratio=1.25)
    real = sum(lengths)
    assert padded_tokens(lengths, batches) <= 1.05 * real
    # 10 条长标题都在第一批里，第一批只会多带很少几条短标题（比例约束 80n <= 1.25*(800+12(n-10)) → n <= 13）
    assert len(batches) == 2 and len(batches[0]) <= 13 and all(lengths[i] == 80 for i in batches[0][:10])
    # 不设比例限制时会凑成一个批，padding 浪费 6 倍
    one = make_batches(lengths, batch_tokens=200_000, max_batch=1024, max_pad_ratio=100)
    assert len(one) == 1 and padded_tokens(lengths, one) == 1000 * 80


def test_make_batches_single_long_item_and_empty():
    assert make_batches([5000], batch_tokens=1024, max_batch=8) == [[0]]
    assert make_batches([], batch_tokens=1024, max_batch=8) == []


def test_shard_name():
    assert shard_name(7) == "part-00007.parquet"


def test_build_inputs_summary_is_sorted_and_recleaned(tmp_path):
    """摘要输入：join 后按 news_id 重排；文本用 summary_raw + 最新 clean_summary 重算（拒答 → 标题）。"""
    import polars as pl
    from text.embed import build_inputs
    ids = [f"{i:024x}" for i in range(6)]
    cand = tmp_path / "cand.parquet"
    pl.DataFrame({"news_id": ids, "title": [f"title {i}" for i in range(6)], "has_body": [True] * 6,
                  "ts_utc": pl.Series([__import__("datetime").datetime(2020, 1, 1)] * 6)}).write_parquet(cand)
    sdir = tmp_path / "summ"; sdir.mkdir()
    # 分片顺序打乱、且只覆盖部分 news_id
    pl.DataFrame({"news_id": [ids[4], ids[1]], "summary_raw": ["Acme beat estimates.", "Foo (FOO) is not mentioned in the article. It discusses Bar."]}).write_parquet(sdir / "part-00001.parquet")
    pl.DataFrame({"news_id": [ids[3]], "summary_raw": ["Here is a summary:\n\nBar raised guidance."]}).write_parquet(sdir / "part-00000.parquet")
    out = tmp_path / "inputs.parquet"
    assert build_inputs(cand, "summary", out, shard_size=2, limit=None, summaries_dir=sdir) == 3
    got = pl.read_parquet(out)
    assert got["news_id"].to_list() == [ids[1], ids[3], ids[4]]
    assert got["text"].to_list() == ["title 1", "Bar raised guidance.", "Acme beat estimates."]
