import datetime as dt

import numpy as np
import polars as pl

from models.ridge_suffstats import add_stats, daily_ic, ic_summary, predict, ridge_path, suffstats


def test_ridge_path_matches_direct_solution_and_additivity():
    rng = np.random.default_rng(0)
    X = rng.standard_normal((300, 7)) * np.array([1, 2, 3, 1, 1, 0.5, 2]) + 5
    B = rng.standard_normal((7, 2))
    Y = X @ B + rng.standard_normal((300, 2)) * 0.1 + np.array([1.0, -2.0])
    st = add_stats([suffstats(X[:120], Y[:120]), suffstats(X[120:], Y[120:])])    # 分块累加 = 整体
    lambdas = [0.1, 10.0, 1000.0]
    betas, intercepts, w = ridge_path(st["XtX"], st["Xsum"], st["Xty"], st["ysum"], int(st["n"]), lambdas)
    Xc, Yc = X - X.mean(0), Y - Y.mean(0)
    for k, lam in enumerate(lambdas):
        direct = np.linalg.solve(Xc.T @ Xc + lam * np.eye(7), Xc.T @ Yc)
        assert np.allclose(betas[k], direct, atol=1e-8)
        assert np.allclose(intercepts[k], Y.mean(0) - X.mean(0) @ direct, atol=1e-8)
    assert np.all(w >= 0) and betas.shape == (3, 7, 2)
    # 小 λ 时拟合接近真值
    assert np.allclose(betas[0], B, atol=0.05)
    pred = predict(X, betas[0, :, 0], intercepts[0, 0])
    assert np.corrcoef(pred, Y[:, 0])[0, 1] > 0.99


def test_daily_ic_and_summary():
    keys = pl.DataFrame({"datetime": [dt.date(2020, 1, 2)] * 6 + [dt.date(2020, 1, 3)] * 6, "instrument": list("ABCDEF") * 2})
    s = np.array([1, 2, 3, 4, 5, 6, 6, 5, 4, 3, 2, 1], dtype=float)
    y = np.array([1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6], dtype=float)
    ic = daily_ic(keys, s, y)
    assert ic["ic"].to_list() == [1.0, -1.0] and ic_summary(ic)["mean"] == 0.0 and ic_summary(ic)["days"] == 2
    # 少于 5 只股票的日子不计
    few = daily_ic(keys.head(3), s[:3], y[:3])
    assert len(few) == 0
