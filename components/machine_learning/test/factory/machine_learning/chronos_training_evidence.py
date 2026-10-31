"""Assertions for genuine deterministic Chronos training evidence."""
from pathlib import Path

import pytest

torch = pytest.importorskip("torch", reason="Chronos LoRA evidence requires the ml group")
peft = pytest.importorskip("peft", reason="Chronos LoRA evidence requires the ml group")
safetensors_torch = pytest.importorskip("safetensors.torch")
get_peft_model = peft.get_peft_model
get_peft_model_state_dict = peft.get_peft_model_state_dict
load_file = safetensors_torch.load_file

from factory.machine_learning.runtime.adapters.chronos_pipeline import load_local_pipeline
from factory.machine_learning.runtime.adapters.chronos_probe_head import ChronosProbeHead
from factory.machine_learning.runtime.adapters.peft_helpers import build_peft_lora_config
from factory.machine_learning.runtime.models import LoRAConfig


def assert_trained_state_changed(
    passport_root: Path, artifact: Path, *, lora: bool, seed: int = 42,
) -> None:
    """Prove probe/adapter updates and copied-backbone byte identity."""
    source = _only_child(passport_root / "backbones" / "chronos-2")
    _assert_same_tree_bytes(source, artifact / "backbone")
    payload = torch.load(artifact / "probe" / "probe.pt", weights_only=True)
    with torch.random.fork_rng():
        torch.manual_seed(seed)
        initial_head = ChronosProbeHead(**payload["probe_constructor"])
    assert any(
        not torch.equal(payload["probe_state_dict"][key], initial)
        for key, initial in initial_head.state_dict().items()
    )
    if lora:
        _assert_adapter_changed(source, artifact, payload, seed)


def _assert_adapter_changed(
    source: Path, artifact: Path, payload: dict, seed: int,
) -> None:
    pipeline = load_local_pipeline(source)
    contract = payload["lora_config"]
    config = LoRAConfig(
        rank=contract["rank"], alpha=contract["alpha"],
        dropout=contract["dropout"], target_modules=contract["target_modules"],
        quantization_bits=contract["quantization_bits"],
    )
    with torch.random.fork_rng():
        torch.manual_seed(seed)
        ChronosProbeHead(**payload["probe_constructor"])
        initial_model = get_peft_model(
            pipeline.inner_model, build_peft_lora_config(config),
        )
        initial = {
            key: value.detach().clone()
            for key, value in get_peft_model_state_dict(initial_model).items()
        }
    trained = load_file(artifact / "adapter" / "adapter_model.safetensors")
    assert set(trained) == set(initial)
    assert any(not torch.equal(trained[key], initial[key]) for key in trained)


def _only_child(root: Path) -> Path:
    children = list(root.iterdir())
    assert len(children) == 1
    return children[0]


def _assert_same_tree_bytes(expected: Path, actual: Path) -> None:
    expected_files = {
        path.relative_to(expected): path.read_bytes()
        for path in expected.rglob("*") if path.is_file()
    }
    actual_files = {
        path.relative_to(actual): path.read_bytes()
        for path in actual.rglob("*") if path.is_file()
    }
    assert actual_files == expected_files


__all__ = ["assert_trained_state_changed"]
