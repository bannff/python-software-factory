"""Real PEFT/LoRA causal-LM training loop.

Split out of :mod:`peft_finetuning` to keep both files under the
200-LOC ceiling. Owns dataset loading (JSONL with a ``"text"`` field
per line — the simplest, most common SFT/CPT text schema; no
established schema exists elsewhere in this brick for free-text
fine-tuning, so this is the documented convention for
:class:`PeftFineTuningAdapter`), tokenization, and the actual
forward/backward/step loop against a ``peft``-wrapped
``transformers`` causal-LM.

Every training objective (``cpt``/``sft``/``dpo``) is trained with
the standard causal-LM cross-entropy loss over the tokenized text —
implementing a full DPO pairwise-preference loss is out of scope for
this task (no DPO dataset schema exists in this brick either); the
adapter still records which ``training_objective`` was requested on
the job for downstream visibility.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import torch

from ..models import LoRAConfig, ResolvedTrainingDataset, TrainingConfig
from .peft_helpers import build_peft_lora_config

__all__ = ["run_peft_training"]


def _load_texts(training_uri: str) -> list[str]:
    """Read a JSONL file of ``{"text": ...}`` records from a ``file://`` URI."""
    path = urlparse(training_uri).path if training_uri.startswith("file://") else training_uri
    texts: list[str] = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        text = record.get("text")
        if not text:
            raise ValueError(f"training record missing required 'text' field: {record!r}")
        texts.append(text)
    if not texts:
        raise ValueError(f"no training records found in {training_uri}")
    return texts


def run_peft_training(
    base_model: str, resolved: ResolvedTrainingDataset,
    training_config: TrainingConfig, lora_config: LoRAConfig | None,
) -> dict[str, Any]:
    """Fine-tune ``base_model`` with LoRA over the resolved dataset.

    Returns a dict with ``loss`` (final real training loss, never
    fabricated) and ``lora_state_dict`` (the trained adapter weights,
    ready for :func:`peft.set_peft_model_state_dict` round-trip).
    """
    from peft import get_peft_model, get_peft_model_state_dict
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.manual_seed(training_config.seed)
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or tokenizer.unk_token

    model = AutoModelForCausalLM.from_pretrained(base_model)
    peft_model = get_peft_model(model, build_peft_lora_config(lora_config or LoRAConfig()))
    peft_model.train()

    texts = _load_texts(resolved.training_uri)
    encodings = tokenizer(
        texts, return_tensors="pt", padding=True, truncation=True,
        max_length=training_config.max_seq_length,
    )
    input_ids, attention_mask = encodings["input_ids"], encodings["attention_mask"]
    labels = input_ids.masked_fill(attention_mask == 0, -100)

    optimizer = torch.optim.AdamW(
        [p for p in peft_model.parameters() if p.requires_grad],
        lr=training_config.learning_rate,
    )

    n = input_ids.shape[0]
    batch_size = min(training_config.batch_size, n)
    steps_per_epoch = max(1, -(-n // batch_size))  # ceil div
    epochs = training_config.epochs or 1
    max_iters = training_config.max_iters or (epochs * steps_per_epoch)

    step = 0
    last_loss = float("nan")
    for _epoch in range(epochs):
        for start in range(0, n, batch_size):
            if step >= max_iters:
                break
            end = min(start + batch_size, n)
            optimizer.zero_grad()
            out = peft_model(
                input_ids=input_ids[start:end],
                attention_mask=attention_mask[start:end],
                labels=labels[start:end],
            )
            out.loss.backward()
            optimizer.step()
            last_loss = float(out.loss.item())
            step += 1
        if step >= max_iters:
            break

    peft_model.eval()
    lora_state_dict = {
        k: v.detach().clone() for k, v in get_peft_model_state_dict(peft_model).items()
    }
    return {"loss": last_loss, "step": step, "lora_state_dict": lora_state_dict}
