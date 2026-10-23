"""模块 4 的 Handler（模块 1 任务 7 先用其中的 Alpha158 变体跑基线）。

Alpha158NoVwap：Qlib 官方 Alpha158 去掉 VWAP0（我们的价格数据只有 OHLCV，没有 vwap；Yahoo 不提供），其余 157 个特征不变。
标签默认改为开盘到开盘 `Ref($open, -2) / Ref($open, -1) - 1`（t+1 开盘买入、t+2 开盘卖出，与新闻 9:00 ET 截止口径一致），
可通过 label 参数覆盖（如收盘到收盘的稳健性口径）。
"""
from __future__ import annotations

from qlib.contrib.data.handler import Alpha158
from qlib.contrib.data.loader import Alpha158DL

LABEL_OPEN_TO_OPEN = ["Ref($open, -2) / Ref($open, -1) - 1"]
LABEL_CLOSE_TO_CLOSE = ["Ref($close, -2) / Ref($close, -1) - 1"]


class Alpha158NoVwap(Alpha158):
    def __init__(self, label=None, **kwargs):
        super().__init__(label=label if label is not None else LABEL_OPEN_TO_OPEN, **kwargs)

    def get_feature_config(self):
        conf = {"kbar": {}, "price": {"windows": [0], "feature": ["OPEN", "HIGH", "LOW"]}, "rolling": {}}
        return Alpha158DL.get_feature_config(conf)
