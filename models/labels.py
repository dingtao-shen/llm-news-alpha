"""模块 3 任务 6 的标签表：用 Qlib 一次算出所有已知口径的标签，写 paths.labels（datetime, instrument, 各标签列）。

标签都相对特征日 t 定义，所以 9:00 与 16:00 两种对齐口径共用同一张表（只是 t 不同）：
  ret_oo    = Ref($open,-2)/Ref($open,-1)-1   主标签：t+1 开盘买入、t+2 开盘卖出
  ret_cc    = Ref($close,-2)/Ref($close,-1)-1 稳健性：收盘到收盘
  ret_oo_dk = Ref($open,-(k+2))/Ref($open,-(k+1))-1  建仓推迟 k 天（k=1..4，新闻动量衰减）
只取成分股区间内的股票-日（D.instruments("sp500")）。运行：make labels（约 1 分钟）。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl

from common import load_paths

LABELS = {
    "ret_oo": "Ref($open,-2)/Ref($open,-1)-1",
    "ret_cc": "Ref($close,-2)/Ref($close,-1)-1",
    **{f"ret_oo_d{k}": f"Ref($open,-{k + 2})/Ref($open,-{k + 1})-1" for k in range(1, 5)},
}
MAIN_LABEL = "ret_oo"


def build_labels(qlib_dir: str, start: str = "2015-01-01", end: str = "2023-12-31") -> pl.DataFrame:
    import qlib
    from qlib.constant import REG_US
    from qlib.data import D
    qlib.init(provider_uri=qlib_dir, region=REG_US)
    df = D.features(D.instruments("sp500"), list(LABELS.values()), start_time=start, end_time=end, freq="day")
    df.columns = list(LABELS.keys())
    df = df.reset_index()
    out = pl.from_pandas(df).rename({"datetime": "datetime", "instrument": "instrument"})
    return out.with_columns(pl.col("datetime").cast(pl.Date)).sort("datetime", "instrument")


def main() -> None:
    paths = load_paths()
    out = Path(paths["labels"])
    if out.exists():
        raise SystemExit(f"{out} exists; delete it first (CLAUDE.md: ask the user before overwriting /workspace/data)")
    df = build_labels(paths["qlib_dir"])
    out.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out, compression="zstd")
    print(f"labels: {len(df):,} stock-days, {df['datetime'].min()}..{df['datetime'].max()}, "
          f"NaN share main label {df[MAIN_LABEL].is_null().mean():.3%} -> {out}")
    print(df.describe())


if __name__ == "__main__":
    main()
