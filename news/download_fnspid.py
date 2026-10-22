"""模块 2 任务 1（下载）：把 FNSPID 的两个新闻 CSV 下载到 paths.raw.fnspid。

数据集 Zihan1004/FNSPID（Hugging Face，gated：需要环境变量 HF_TOKEN，脚本不打印它）。
已存在且字节数与 Hub 元数据一致的文件跳过；完成后写 MANIFEST.json（文件名、大小、sha256(xet hash)、revision、时间）。
长任务：bash infra/run_bg.sh fnspid-download python -m news.download_fnspid
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

from common import load_paths

REPO = "Zihan1004/FNSPID"
FILES = ["Stock_news/nasdaq_exteral_data.csv", "Stock_news/All_external.csv"]


def main() -> None:
    assert os.environ.get("HF_TOKEN"), "HF_TOKEN not set"
    out = Path(load_paths()["raw"]["fnspid_news"])
    out.mkdir(parents=True, exist_ok=True)
    api = HfApi()
    info = api.dataset_info(REPO, files_metadata=True)
    meta = {s.rfilename: s for s in info.siblings}
    manifest = {"repo": REPO, "revision": info.sha, "files": []}
    for f in FILES:
        target = out / Path(f).name
        expected = meta[f].size
        if target.exists() and target.stat().st_size == expected:
            print(f"skip {target.name}: exists with expected size {expected:,}", flush=True)
        else:
            t0 = time.time()
            print(f"downloading {f} ({expected / 1e9:.2f} GB) ...", flush=True)
            # local_dir 保留子目录结构，下载后移到 out/ 根下
            p = Path(hf_hub_download(REPO, f, repo_type="dataset", revision=info.sha, local_dir=str(out)))
            if p.resolve() != target.resolve():
                p.replace(target)
            dtime = time.time() - t0
            size = target.stat().st_size
            print(f"done {target.name}: {size:,} bytes in {dtime / 60:.1f} min ({size / dtime / 1e6:.0f} MB/s)", flush=True)
            assert size == expected, f"size mismatch {size} != {expected}"
        lfs = getattr(meta[f], "lfs", None)
        manifest["files"].append({"name": target.name, "hub_path": f, "size": expected,
                                  "sha256": getattr(lfs, "sha256", None) if lfs else None})
    manifest["downloaded_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("manifest:", json.dumps(manifest, indent=2), flush=True)
    for d in (out / "Stock_news", out / ".cache"):
        if d.exists() and not any(d.iterdir()):
            d.rmdir()


if __name__ == "__main__":
    main()
