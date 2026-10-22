"""模块 1 任务 1：S&P 500 时点成分股 → Qlib `instruments/sp500.txt` 与 2015–2023 ticker 全集。

数据源：shardul0701/SP500-Survivorship-bias-data-2004-2026（MIT），每年一个 YAML，
已按固定 commit 拷贝到仓库 `data/universe_src/`（见同目录 SOURCE.md），构建不依赖网络。

回放规则：
- 以起始年的 `tickers_on_Jan_1` 为初始集合，按日期顺序应用所有 `changes`
  （`difference` = 当日移出，`union` = 当日加入；其余键如 confidence_score 忽略）。
- 每只 ticker 得到一个或多个在池区间 [start, end]（含两端）：加入日起算成分股，退出日前一天为区间末。
- 起点钳到 START，仍在池内的 end 记 END；同一 ticker 多次进出写多行（Qlib instruments 允许）。
- 不做任何代码合并或映射：FB 与 META、GOOG 与 GOOGL 都各自保留。

运行：make universe（Pod）。写出 Qlib instruments、membership parquet、results/universe/ 下的全集与汇总。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

from common import ROOT, load_paths

SRC_DIR = ROOT / "data" / "universe_src"
START, END = dt.date(2015, 1, 1), dt.date(2023, 12, 31)


@dataclass(frozen=True)
class Interval:
    ticker: str
    start: dt.date
    end: dt.date


def load_year(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _parse_date(s: str | dt.date) -> dt.date:
    return s if isinstance(s, dt.date) else dt.date.fromisoformat(str(s))


def build_intervals(years: list[dict], start: dt.date = START, end: dt.date = END) -> list[Interval]:
    """由按年排序的 YAML 字典列表回放成分股区间。"""
    years = sorted(years, key=lambda d: int(d["year"]))
    assert int(years[0]["year"]) == start.year, "第一个 YAML 必须是起始年"
    events: list[tuple[dt.date, str, list[str]]] = []
    for d in years:
        for date_str, entry in (d.get("changes") or {}).items():
            date = _parse_date(date_str)
            events.append((date, "remove", list(entry.get("difference") or [])))
            events.append((date, "add", list(entry.get("union") or [])))
    # 同一天先移出再加入，保证 FB→META 这类同日替换顺序确定
    events.sort(key=lambda e: (e[0], 0 if e[1] == "remove" else 1))

    open_since: dict[str, dt.date] = {str(t): start for t in years[0]["tickers_on_Jan_1"]}
    out: list[Interval] = []
    for date, kind, tickers in events:
        if date < start or date > end:
            continue
        for t in map(str, tickers):
            if kind == "remove":
                if t in open_since:  # 退出日前一天为区间末
                    out.append(Interval(t, open_since.pop(t), date - dt.timedelta(days=1)))
            else:
                open_since.setdefault(t, date)
    out.extend(Interval(t, s, end) for t, s in open_since.items())
    out = [iv for iv in out if iv.start <= iv.end]
    return sorted(out, key=lambda iv: (iv.ticker, iv.start))


def members_on(intervals: list[Interval], day: dt.date) -> set[str]:
    return {iv.ticker for iv in intervals if iv.start <= day <= iv.end}


def continuity_report(years: list[dict], intervals: list[Interval]) -> list[str]:
    """校验：YAML 第 Y+1 年 Jan-1 名单应等于回放到 Y 年末的集合。返回不一致的描述。"""
    msgs = []
    by_year = {int(d["year"]): d for d in years}
    for y in sorted(by_year):
        if y + 1 not in by_year:
            continue
        replayed = members_on(intervals, dt.date(y, 12, 31))
        declared = set(map(str, by_year[y + 1]["tickers_on_Jan_1"]))
        if replayed != declared:
            msgs.append(f"{y}-12-31 replay vs {y + 1} Jan-1: only_replay={sorted(replayed - declared)} "
                        f"only_declared={sorted(declared - replayed)}")
    return msgs


def write_instruments(intervals: list[Interval], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for iv in intervals:
            fh.write(f"{iv.ticker}\t{iv.start.isoformat()}\t{iv.end.isoformat()}\n")


def summary_rows(intervals: list[Interval], years: list[dict]) -> list[dict]:
    rows = []
    for d in sorted(years, key=lambda d: int(d["year"])):
        y = int(d["year"])
        adds = removes = 0
        for date_str, entry in (d.get("changes") or {}).items():
            adds += len(entry.get("union") or [])
            removes += len(entry.get("difference") or [])
        rows.append({
            "year": y,
            "members_jan1_yaml": len(d["tickers_on_Jan_1"]),
            "members_dec31_replay": len(members_on(intervals, dt.date(y, 12, 31))),
            "change_dates": len(d.get("changes") or {}),
            "additions": adds,
            "removals": removes,
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(SRC_DIR))
    args = ap.parse_args()
    paths = load_paths()

    files = sorted(Path(args.src).glob("sp500-ticker-changes-*.yaml"))
    years = [load_year(f) for f in files if START.year <= int(f.stem.split("-")[-1]) <= END.year]
    intervals = build_intervals(years)

    inst = Path(paths["qlib_dir"]) / "instruments" / "sp500.txt"
    write_instruments(intervals, inst)

    import polars as pl
    df = pl.DataFrame({"ticker": [iv.ticker for iv in intervals],
                       "start": [iv.start for iv in intervals],
                       "end": [iv.end for iv in intervals]})
    raw_dir = Path(paths["raw"]["universe"]); raw_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(raw_dir / "sp500_membership.parquet")

    res = ROOT / paths["results"] / "universe"; res.mkdir(parents=True, exist_ok=True)
    tickers = sorted({iv.ticker for iv in intervals})
    (res / "sp500_tickers_2015_2023.txt").write_text("\n".join(tickers) + "\n")
    pl.DataFrame(summary_rows(intervals, years)).write_csv(res / "sp500_summary.csv")

    multi = Counter(iv.ticker for iv in intervals)
    meta = {
        "source": "shardul0701/SP500-Survivorship-bias-data-2004-2026 @ 40a9ddc31bb421b93186e321333d05c07e5d1dd3",
        "range": [START.isoformat(), END.isoformat()],
        "n_tickers": len(tickers), "n_intervals": len(intervals),
        "n_tickers_multi_interval": sum(1 for c in multi.values() if c > 1),
        "members_start": len(members_on(intervals, START)), "members_end": len(members_on(intervals, END)),
        "continuity_issues": continuity_report(years, intervals),
    }
    (res / "sp500_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"wrote {inst} ({len(intervals)} lines), {raw_dir / 'sp500_membership.parquet'}, {res}/")


if __name__ == "__main__":
    main()
