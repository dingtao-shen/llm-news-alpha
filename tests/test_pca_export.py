import numpy as np

from models.pca_export import fit_pca, transform


def test_pca_recovers_low_rank_structure():
    rng = np.random.default_rng(0)
    B = rng.standard_normal((5, 40)); X = rng.standard_normal((500, 5)) @ B + 3.0 + 0.01 * rng.standard_normal((500, 40))
    pca = fit_pca(X.astype(np.float32), k=8)
    assert pca["components"].shape == (8, 40) and pca["explained_variance_ratio"][:5].sum() > 0.99
    Z = transform(X.astype(np.float32), pca)
    assert Z.shape == (500, 8) and abs(Z[:, :5].mean()) < 1e-3          # 中心化后均值 ≈ 0
    # 新样本用同一均值 / 主成分变换（不重新拟合）
    Z2 = transform(X[:10].astype(np.float32), pca); assert np.allclose(Z2, Z[:10], atol=1e-4)
