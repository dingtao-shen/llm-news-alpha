import numpy as np
import pandas as pd

from analysis.longshort import ewct, portfolio_series, quintile_weights, summarize


def test_quintile_weights_and_returns():
    idx = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])
    cols = list("ABCDEFGHIJ")
    scores = pd.DataFrame(np.nan, index=idx, columns=cols)
    scores.loc[idx[0]] = np.arange(10)                 # A 最低 … J 最高
    scores.loc[idx[1], ["A", "B", "C"]] = [1, 2, 3]     # 只有 3 只 → 不足 10 只，空仓
    W = quintile_weights(scores)
    assert W.loc[idx[0], "J"] == 0.5 and W.loc[idx[0], "I"] == 0.5 and W.loc[idx[0], "A"] == -0.5 and W.loc[idx[0], "B"] == -0.5
    assert abs(W.loc[idx[0]].sum()) < 1e-12 and W.loc[idx[0]].abs().sum() == 2.0
    assert (W.loc[idx[1]] == 0).all() and (W.loc[idx[2]] == 0).all()
    R = pd.DataFrame(0.01, index=idx, columns=cols); R.loc[idx[0], ["I", "J"]] = 0.03; R.loc[idx[0], ["A", "B"]] = -0.01
    ps = portfolio_series(W, R)
    assert abs(ps.loc[idx[0], "gross"] - (0.03 - (-0.01))) < 1e-12          # 多头均值 − 空头均值
    assert ps.loc[idx[0], "turnover"] == 2.0 and ps.loc[idx[1], "turnover"] == 2.0 and ps.loc[idx[2], "turnover"] == 0.0


def test_ewct_recursion_and_cost():
    idx = pd.to_datetime(["2020-01-02", "2020-01-03"])
    Wt = pd.DataFrame([[1.0, -1.0], [-1.0, 1.0]], index=idx, columns=["A", "B"])
    W = ewct(Wt, 0.5)
    assert np.allclose(W.iloc[0], [0.5, -0.5]) and np.allclose(W.iloc[1], [0.5 * -1 + 0.5 * 0.5, 0.5 * 1 + 0.5 * -0.5])
    assert ewct(Wt, 1.0).equals(Wt)
    R = pd.DataFrame(0.0, index=idx, columns=["A", "B"])
    ps = portfolio_series(Wt, R)
    s = summarize(ps, cost_bps=10)
    assert s["turnover_daily"] == 3.0                  # 第 1 天 2.0，第 2 天 4.0（完全反向）
    assert abs(s["ann_return_net"] - (-10 / 1e4 * 3.0 * 252)) < 1e-12


def test_value_weights_and_decile():
    idx = pd.to_datetime(["2020-01-02"]); cols = list("ABCDEFGHIJKL")       # 12 只，每组 ⌊12/5⌋ = 2 只
    scores = pd.DataFrame([np.arange(12)], index=idx, columns=cols, dtype=float)
    size = pd.DataFrame([[1.0] * 10 + [3.0, 1.0]], index=idx, columns=cols)
    W = quintile_weights(scores, size=size)
    assert abs(W.loc[idx[0], "K"] - 0.75) < 1e-12 and abs(W.loc[idx[0], "L"] - 0.25) < 1e-12 and W.loc[idx[0], "A"] == -0.5
    size.loc[idx[0], "L"] = np.nan                       # 缺市值 → 不入组合；剩 11 只，最高两只变成 J、K
    W = quintile_weights(scores, size=size)
    assert W.loc[idx[0], "L"] == 0 and abs(W.loc[idx[0], "K"] - 0.75) < 1e-12 and abs(W.loc[idx[0], "J"] - 0.25) < 1e-12
    W10 = quintile_weights(scores, n_groups=10)          # 十分组：每组 1 只
    assert W10.loc[idx[0], "L"] == 1.0 and W10.loc[idx[0], "A"] == -1.0 and (W10.loc[idx[0]] != 0).sum() == 2
