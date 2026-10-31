"""Exhaustive executable identity, lifecycle, and dependency gate."""

from __future__ import annotations

import platform
import re
import subprocess
import sys
from pathlib import Path

import pytest
from factory.machine_learning.runtime.passport_native_contract import (
    native_conformance_identity,
)

from .native_portfolio_matrix import EXPECTED_NAMES, PORTFOLIO

_ROOT = Path(__file__).parents[5]
_MLX_MARKER = '; platform_system == "Darwin" and platform_machine == "arm64"'
_PINNED = {
    "chronos-forecasting": "chronos-forecasting==2.3.1",
    "lightgbm": "lightgbm==4.7.0",
    "mlflow": "mlflow==3.16.0",
    "mlx": f"mlx==0.31.1{_MLX_MARKER}",
    "mlx-lm": f"mlx-lm==0.31.2{_MLX_MARKER}",
    "ncps": "ncps==1.0.1",
    "peft": "peft==0.19.1",
    "torch": "torch==2.13.0",
    "transformers": "transformers==5.5.4",
}
_EXPECTED_IDENTITIES = {
    "lightgbm": (
        "lightgbm",
        "4.7.0",
        "mlflow",
        "3.16.0",
        "mlflow.lightgbm",
        "mlflow-lightgbm",
        "lightgbm",
        "local-lightgbm-isolated-v1",
    ),
    "torch-lstm": (
        "torch",
        "2.13.0",
        "torch",
        "2.13.0",
        "torch.state_dict",
        "pytorch",
        "torch",
        "local-torch-isolated-v1",
    ),
    "torch-tcn": (
        "torch",
        "2.13.0",
        "torch",
        "2.13.0",
        "torch.state_dict",
        "pytorch",
        "torch",
        "local-torch-isolated-v1",
    ),
    "patchtst": (
        "transformers",
        "5.5.4",
        "transformers",
        "5.5.4",
        "transformers.patchtst",
        "transformers-patchtst",
        "patchtst",
        "local-patchtst-isolated-v1",
    ),
    "lnn-ltc": (
        "ncps",
        "1.0.1",
        "ncps",
        "1.0.1",
        "ncps.torch.LTC.state_dict",
        "pytorch",
        "lnn",
        "local-ncps-ltc-isolated-v1",
    ),
    "chronos": (
        "chronos-forecasting",
        "2.3.1",
        "chronos-forecasting",
        "2.3.1",
        "chronos.Chronos2Pipeline",
        "chronos2-native-probe",
        "chronos2",
        "local-chronos2-isolated-v1",
    ),
    "mlx-lstm": (
        "mlx",
        "0.31.1",
        "mlx",
        "0.31.1",
        "mlx.nn.Module.load_weights",
        "mlx-safetensors",
        "mlx",
        "local-mlx-isolated-v1",
    ),
    "mlx-tcn": (
        "mlx",
        "0.31.1",
        "mlx",
        "0.31.1",
        "mlx.nn.Module.load_weights",
        "mlx-safetensors",
        "mlx",
        "local-mlx-isolated-v1",
    ),
}


def _name(requirement: str) -> str:
    return re.split(r"[<>=!~;\[]", requirement, maxsplit=1)[0].strip().lower()


def _canonical(requirement: str) -> str:
    return " ".join(requirement.replace("'", '"').split())


def _selected(requirements: list[str]) -> dict[str, str]:
    return {_name(item): _canonical(item) for item in requirements if _name(item) in _PINNED}


def _pinned_version(requirement: str) -> str:
    match = re.search(r"==([^;]+)", requirement)
    assert match is not None
    return match.group(1).strip()


def _identity(case) -> tuple[str, ...]:
    return (
        case.framework,
        case.framework_version,
        case.package,
        case.package_version,
        case.loader,
        case.artifact_format,
        case.identity_family,
        case.verifier,
    )


def test_portfolio_is_complete_frozen_and_exact() -> None:
    assert len(PORTFOLIO) == len(EXPECTED_NAMES)
    assert {case.name for case in PORTFOLIO} == EXPECTED_NAMES
    assert {case.name: _identity(case) for case in PORTFOLIO} == _EXPECTED_IDENTITIES


@pytest.mark.parametrize("case", PORTFOLIO, ids=lambda case: case.name)
def test_canonical_identity_and_executable_evidence(case) -> None:
    assert native_conformance_identity(case.loader) == (
        case.identity_family,
        case.verifier,
    )
    nodes = {
        case.evidence.lifecycle,
        case.evidence.strict,
        case.evidence.authority,
    }
    if case.name == "lnn-ltc":
        assert case.evidence.timespan is not None
        nodes.add(case.evidence.timespan)
    else:
        assert case.evidence.timespan is None
    assert all(node.startswith("components/machine_learning/test/") for node in nodes)


def test_all_supported_portfolio_evidence_nodes_collect() -> None:
    cases = PORTFOLIO
    if sys.platform != "darwin" or platform.machine() != "arm64":
        cases = tuple(case for case in cases if not case.name.startswith("mlx-"))
    nodes = sorted(
        {
            node
            for case in cases
            for node in (
                case.evidence.lifecycle,
                case.evidence.strict,
                case.evidence.authority,
                case.evidence.timespan,
            )
            if node is not None
        }
    )
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *nodes],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert all(node in completed.stdout for node in nodes)


def test_unknown_loader_is_not_trusted() -> None:
    with pytest.raises(ValueError, match="not approved"):
        native_conformance_identity("untrusted.loader")
