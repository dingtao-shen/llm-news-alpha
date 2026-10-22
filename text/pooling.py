"""均值池化（与 infra/smoke_embed.py 一致）：最后一层隐状态按 attention_mask 做掩码平均，float32 计算。"""
from __future__ import annotations

import torch


def masked_mean(hidden: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """hidden: (B, T, H) 任意 dtype；mask: (B, T) 0/1。返回 (B, H) float32。"""
    m = mask.unsqueeze(-1).to(torch.float32)
    return (hidden.float() * m).sum(1) / m.sum(1).clamp_min(1.0)
