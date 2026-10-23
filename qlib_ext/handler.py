"""模块 4 的 Handler。

Alpha158NoVwap：Qlib 官方 Alpha158 去掉 VWAP0（我们的价格数据只有 OHLCV，没有 vwap；Yahoo 不提供），其余 157 个特征不变。
标签默认改为开盘到开盘 `Ref($open, -2) / Ref($open, -1) - 1`（t+1 开盘买入、t+2 开盘卖出，与新闻 9:00 ET 截止口径一致），
可通过 label 参数覆盖（如收盘到收盘的稳健性口径）。

NewsAlpha158Handler：在 paths.qlib_news_dir 这套数据上，特征 = Alpha158NoVwap 的 157 个（feature_set 含 "alpha158"）
+ 新闻 PCA-64（$pct_0..63 标题 / $pcb_0..63 原文，news_text 选 title / body）+ $news_cnt_x + $has_news_x（feature_set 含 "news"）。
没有新闻的股票-日新闻特征为 0，has_news 进特征让模型区分"中性新闻"和"没有新闻"。
推断期处理器：RobustZScoreNorm（截面标准化、裁剪离群值）+ Fillna；学习期：DropnaLabel + CSRankNorm。标准化的 fit_start/fit_end 必须是该滚动窗口的训练期。
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


from qlib.data.dataset.handler import DataHandlerLP
from qlib.contrib.data.handler import check_transform_proc

_INFER = [{"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
          {"class": "Fillna", "kwargs": {"fields_group": "feature"}}]
_LEARN = [{"class": "DropnaLabel"}, {"class": "CSRankNorm", "kwargs": {"fields_group": "label"}}]


class NewsAlpha158Handler(DataHandlerLP):
    def __init__(self, instruments="sp500", start_time=None, end_time=None, freq="day", fit_start_time=None, fit_end_time=None,
                 feature_set=("alpha158", "news"), news_text="body", n_emb=64, label=None,
                 infer_processors=_INFER, learn_processors=_LEARN, process_type=DataHandlerLP.PTYPE_A, **kwargs):
        infer_processors = check_transform_proc(infer_processors, fit_start_time, fit_end_time)
        learn_processors = check_transform_proc(learn_processors, fit_start_time, fit_end_time)
        fields, names = [], []
        if "alpha158" in feature_set:
            f, n = Alpha158DL.get_feature_config({"kbar": {}, "price": {"windows": [0], "feature": ["OPEN", "HIGH", "LOW"]}, "rolling": {}})
            fields += f; names += n
        if "news" in feature_set:
            p = {"title": "pct", "body": "pcb"}[news_text]; sfx = p[-1]
            fields += [f"${p}_{i}" for i in range(n_emb)] + [f"$news_cnt_{sfx}", f"$has_news_{sfx}"]
            names += [f"EMB{i}" for i in range(n_emb)] + ["NEWS_CNT", "HAS_NEWS"]
        data_loader = {"class": "QlibDataLoader", "kwargs": {"config": {"feature": (fields, names),
                                                                        "label": (label or LABEL_OPEN_TO_OPEN, ["LABEL0"])}, "freq": freq}}
        super().__init__(instruments=instruments, start_time=start_time, end_time=end_time, data_loader=data_loader,
                         infer_processors=infer_processors, learn_processors=learn_processors, process_type=process_type, **kwargs)
