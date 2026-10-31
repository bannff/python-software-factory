"""Chronos-2 pooled-embedding classifier probe training and inference."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from ..models import LoRAConfig
from .chronos_identity import exact_lora_config, lora_contract
from .chronos_pipeline import encode_batch
from .chronos_probe_head import ChronosProbeHead
from .chronos_scoring import score_chronos_classifier
from .peft_helpers import build_peft_lora_config
from .temporal_split import temporal_split_with_shuffle_fallback
from .timeseries_metrics import compute_classification_metrics
from .torch_data import apply_scaler, fit_scaler_transform, load_array, to_windows


def train_probe(
    pipeline: "object", adapter_dir: Path, X_uri: str, y_uri: str,
    window_size: int, epochs: int, batch_size: int, learning_rate: float,
    validation_split: float, seed: int, early_stopping_patience: int,
    lora: bool, lora_config: LoRAConfig | None,
) -> tuple[ChronosProbeHead, dict[str, float], dict[str, Any]]:
    """Train a frozen-backbone probe or a public-PEFT LoRA probe."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    X = to_windows(load_array(X_uri), window_size).astype(np.float32)
    y = load_array(y_uri).ravel().astype(np.int64)
    if len(X) != len(y) or not len(y):
        raise ValueError("Chronos X/y windows are empty or misaligned")
    classes = max(int(y.max()) + 1, 2)
    Xt, yt, Xv_raw, yv = temporal_split_with_shuffle_fallback(
        X, y, validation_split, seed,
    )
    Xt, mean, scale = fit_scaler_transform(Xt, len(Xt))
    Xv = apply_scaler(Xv_raw, mean, scale)
    base_model = pipeline.inner_model
    d_model = int(base_model.config.d_model)
    head = ChronosProbeHead(d_model, classes)
    peft_model = None
    contract = None
    if lora:
        exact = exact_lora_config(lora_config)
        contract = lora_contract(exact)
        from peft import get_peft_model
        peft_model = get_peft_model(base_model, build_peft_lora_config(exact))
        encode_model = peft_model
        trainable = [parameter for parameter in peft_model.parameters() if parameter.requires_grad]
    else:
        for parameter in base_model.parameters():
            parameter.requires_grad_(False)
        encode_model, trainable = base_model, []
    optimizer = optim.Adam([*head.parameters(), *trainable], lr=learning_rate)
    yt_tensor, yv_tensor = torch.from_numpy(yt), torch.from_numpy(yv)
    best_loss, best_state, stale = float("inf"), None, 0
    rng = np.random.default_rng(seed)
    for _ in range(epochs):
        head.train()
        order = rng.permutation(len(Xt))
        for start in range(0, len(Xt), batch_size):
            indices = order[start:start + batch_size]
            optimizer.zero_grad()
            embeddings = encode_batch(
                encode_model, Xt[indices].transpose(0, 2, 1), lora,
            )
            loss = nn.functional.cross_entropy(head(embeddings), yt_tensor[indices])
            loss.backward()
            torch.nn.utils.clip_grad_norm_([*head.parameters(), *trainable], 1.0)
            optimizer.step()
        head.eval()
        with torch.no_grad():
            validation = encode_batch(encode_model, Xv.transpose(0, 2, 1), False)
            value = nn.functional.cross_entropy(head(validation), yv_tensor).item()
        if value < best_loss - 1e-6:
            best_loss = value
            best_state = {key: tensor.detach().clone() for key, tensor in head.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= early_stopping_patience:
                break
    head.load_state_dict(best_state or head.state_dict(), strict=True)
    validation_probabilities = score_chronos_classifier(
        encode_model, head, Xv_raw, mean, scale,
    )
    metrics = compute_classification_metrics(
        yv, validation_probabilities.argmax(axis=1), validation_probabilities[:, 1],
    )
    if peft_model is not None:
        peft_model.save_pretrained(adapter_dir, safe_serialization=True)
        peft_model.unload()
    return head, metrics, {
        "d_model": d_model, "input_size": X.shape[-1], "num_classes": classes,
        "scaler_mean": mean, "scaler_scale": scale,
        "adapter_mode": "lora" if lora else "frozen", "lora_config": contract,
        "val_y_true": yv.astype(float).tolist(),
        "val_y_pred": validation_probabilities.argmax(axis=1).astype(float).tolist(),
        "val_y_score": validation_probabilities[:, 1].tolist(),
    }


__all__ = ["train_probe"]
