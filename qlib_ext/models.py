"""模块 4–5 的 Model 封装。

RidgeModel：sklearn Ridge（用于 PCA / Alpha158 这种几百维特征），alpha 在验证段按日均 Rank IC 从网格里选；测试段只预测一次。
ExternalPredModel：读取全维 Ridge 的样本外预测（接口文件 3），fit 为空，predict 按 segment 的索引 reindex，让外部预测也能走 Qlib 的记录与回测。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from qlib.data.dataset.handler import DataHandlerLP
from qlib.model.base import Model
from sklearn.linear_model import Ridge


def daily_rank_ic(pred: pd.Series, label: pd.Series) -> float:
    df = pd.DataFrame({"p": pred, "y": label}).dropna()
    ic = df.groupby(level="datetime").apply(lambda g: g["p"].corr(g["y"], method="spearman") if len(g) >= 5 else np.nan)
    return float(ic.mean())


class RidgeModel(Model):
    def __init__(self, alphas=(1.0, 10.0, 100.0, 1000.0, 10000.0), fit_intercept=True):
        self.alphas = list(alphas); self.fit_intercept = fit_intercept
        self.model = None; self.alpha_ = None; self.valid_ic_ = {}

    def fit(self, dataset, **kwargs):
        tr = dataset.prepare("train", col_set=["feature", "label"], data_key=DataHandlerLP.DK_L)
        x, y = tr["feature"].values, tr["label"].values.ravel()
        if "valid" in dataset.segments:
            va = dataset.prepare("valid", col_set=["feature", "label"], data_key=DataHandlerLP.DK_L)
            for a in self.alphas:
                m = Ridge(alpha=a, fit_intercept=self.fit_intercept).fit(x, y)
                self.valid_ic_[a] = daily_rank_ic(pd.Series(m.predict(va["feature"].values), index=va.index), va["label"].iloc[:, 0])
            self.alpha_ = max(self.valid_ic_, key=lambda k: (self.valid_ic_[k] if not np.isnan(self.valid_ic_[k]) else -9))
        else:
            self.alpha_ = self.alphas[len(self.alphas) // 2]
        self.model = Ridge(alpha=self.alpha_, fit_intercept=self.fit_intercept).fit(x, y)

    def predict(self, dataset, segment="test"):
        x = dataset.prepare(segment, col_set="feature", data_key=DataHandlerLP.DK_I)
        return pd.Series(self.model.predict(x.values), index=x.index)


class ExternalPredModel(Model):
    def __init__(self, pred_path: str, score_col: str = "score"):
        df = pd.read_parquet(pred_path)
        df["datetime"] = pd.to_datetime(df["datetime"])
        self.pred = df.set_index(["datetime", "instrument"])[score_col]

    def fit(self, dataset, **kwargs):
        pass

    def predict(self, dataset, segment="test"):
        idx = dataset.prepare(segment, col_set="feature", data_key=DataHandlerLP.DK_I).index
        return self.pred.reindex(idx)
