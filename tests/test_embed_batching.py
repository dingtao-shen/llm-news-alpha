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


def test_make_batches_single_long_item_and_empty():
    assert make_batches([5000], batch_tokens=1024, max_batch=8) == [[0]]
    assert make_batches([], batch_tokens=1024, max_batch=8) == []


def test_shard_name():
    assert shard_name(7) == "part-00007.parquet"
