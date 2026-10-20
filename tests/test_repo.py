"""骨架级测试：保证 Mac 和 Pod 上 `make test` 都能跑通。后续模块在这里加真正的单元测试。"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_paths_yaml_has_interface_files():
    cfg = yaml.safe_load((ROOT / "paths.yaml").read_text())
    assert cfg["news"]["clean"].endswith("news_clean.parquet")
    assert "emb_dir" in cfg and "pred_dir" in cfg
    assert cfg["models"]["llama3_base"] == "meta-llama/Meta-Llama-3-8B"


def test_packages_importable():
    import analysis, data, models, news, qlib_ext, text  # noqa: F401
