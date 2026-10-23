import numpy as np

from analysis.dm_test import nw_tstat


def test_nw_tstat_iid_and_autocorrelated():
    rng = np.random.default_rng(0)
    x = rng.standard_normal(2000) + 0.1
    mu, t = nw_tstat(x, lag=5)
    assert abs(mu - x.mean()) < 1e-12 and 3 < t < 6          # iid：t ≈ 0.1 / (1/√2000) ≈ 4.5
    # 正自相关序列的 HAC t 应小于朴素 t
    e = np.zeros(2000)
    for i in range(1, 2000):
        e[i] = 0.7 * e[i - 1] + rng.standard_normal()
    y = e + 0.1
    naive = y.mean() / (y.std(ddof=1) / np.sqrt(len(y)))
    assert nw_tstat(y, lag=5)[1] < naive
