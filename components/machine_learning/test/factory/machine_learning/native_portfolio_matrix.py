"""Frozen native CAN portfolio identity and executable evidence contract."""
from dataclasses import dataclass


_TEST_ROOT = "components/machine_learning/test/factory/machine_learning"


def _node(module: str, test: str) -> str:
    return f"{_TEST_ROOT}/{module}::{test}"


@dataclass(frozen=True)
class PortfolioEvidence:
    """Executable nodes for lifecycle, strict rejection, and cold authority."""

    lifecycle: str
    strict: str
    authority: str
    timespan: str | None = None


@dataclass(frozen=True)
class NativePortfolioCase:
    name: str
    framework: str
    framework_version: str
    package: str
    package_version: str
    loader: str
    artifact_format: str
    identity_family: str
    verifier: str
    evidence: PortfolioEvidence


_NEURAL_LIFECYCLE = "test_neural_passport_subprocess.py"
_NEURAL_STRICT = "test_neural_passport_strict_contracts.py"
_NEURAL_AUTHORITY = "test_neural_passport_mcp.py"
_MLX_LIFECYCLE = "test_mlx_passport_lifecycle.py"
_MLX_STRICT = "test_mlx_passport_strict.py"


def _neural_evidence(name: str, strict: str) -> PortfolioEvidence:
    return PortfolioEvidence(
        _node(_NEURAL_LIFECYCLE, f"test_native_candidate_promotes_and_fresh_scores_match[{name}]"),
        _node(_NEURAL_STRICT, strict),
        _node(_NEURAL_AUTHORITY, f"test_mcp_cold_scores_exact_ref_without_warm_cache[{name}]"),
    )


def _mlx_evidence(name: str) -> PortfolioEvidence:
    lifecycle = _node(
        _MLX_LIFECYCLE, f"test_mlx_candidate_promotes_and_mcp_fresh_scores_match[{name}]",
    )
    return PortfolioEvidence(
        lifecycle,
        _node(
            _MLX_STRICT,
            f"test_mlx_metadata_and_loader_reject_constructor_scaler_shape_and_bytes[{name}]",
        ),
        lifecycle,
    )


PORTFOLIO = (
    NativePortfolioCase(
        "lightgbm", "lightgbm", "4.7.0", "mlflow", "3.16.0",
        "mlflow.lightgbm", "mlflow-lightgbm", "lightgbm",
        "local-lightgbm-isolated-v1", PortfolioEvidence(
            _node("test_lightgbm_passport_subprocess.py", "test_candidate_promotes_then_cold_predicts_and_tamper_fails_before_scoring"),
            _node("test_lightgbm_passport_subprocess.py", "test_candidate_promotes_then_cold_predicts_and_tamper_fails_before_scoring"),
            _node("test_lightgbm_passport_subprocess.py", "test_candidate_promotes_then_cold_predicts_and_tamper_fails_before_scoring"),
        ),
    ),
    NativePortfolioCase(
        "torch-lstm", "torch", "2.13.0", "torch", "2.13.0",
        "torch.state_dict", "pytorch", "torch", "local-torch-isolated-v1",
        _neural_evidence(
            "lstm", "test_torch_passport_rejects_type_revision_constructor_and_classes[lstm]",
        ),
    ),
    NativePortfolioCase(
        "torch-tcn", "torch", "2.13.0", "torch", "2.13.0",
        "torch.state_dict", "pytorch", "torch", "local-torch-isolated-v1",
        _neural_evidence(
            "tcn", "test_torch_passport_rejects_type_revision_constructor_and_classes[tcn]",
        ),
    ),
    NativePortfolioCase(
        "patchtst", "transformers", "5.5.4", "transformers", "5.5.4",
        "transformers.patchtst", "transformers-patchtst", "patchtst",
        "local-patchtst-isolated-v1", _neural_evidence(
            "patchtst", "test_patchtst_passport_rejects_config_classes_and_threshold",
        ),
    ),
    NativePortfolioCase(
        "lnn-ltc", "ncps", "1.0.1", "ncps", "1.0.1",
        "ncps.torch.LTC.state_dict", "pytorch", "lnn",
        "local-ncps-ltc-isolated-v1", PortfolioEvidence(
            _node("test_lnn_passport_acceptance.py", "test_lnn_candidate_promotion_cold_and_fresh_process_parity"),
            _node("test_lnn_passport_acceptance.py", "test_all_lnn_tamper_classes_fail_before_ltc_execution"),
            _node("test_neural_passport_mcp.py", "test_mcp_lnn_requires_valid_live_timing_without_training_comparison"),
            _node("test_lnn_passport_acceptance.py", "test_all_lnn_tamper_classes_fail_before_ltc_execution"),
        ),
    ),
    NativePortfolioCase(
        "chronos", "chronos-forecasting", "2.3.1", "chronos-forecasting",
        "2.3.1", "chronos.Chronos2Pipeline", "chronos2-native-probe",
        "chronos2", "local-chronos2-isolated-v1", PortfolioEvidence(
            _node(_NEURAL_LIFECYCLE, "test_native_candidate_promotes_and_fresh_scores_match[chronos]"),
            _node("test_chronos_passport_strict.py", "test_chronos_passport_identity_and_scaler_mismatches_fail"),
            _node("test_chronos_passport_mcp.py", "test_mcp_chronos_exact_promoted_ref_has_no_timing[False]"),
        ),
    ),
    NativePortfolioCase(
        "mlx-lstm", "mlx", "0.31.1", "mlx", "0.31.1",
        "mlx.nn.Module.load_weights", "mlx-safetensors", "mlx",
        "local-mlx-isolated-v1", _mlx_evidence("lstm"),
    ),
    NativePortfolioCase(
        "mlx-tcn", "mlx", "0.31.1", "mlx", "0.31.1",
        "mlx.nn.Module.load_weights", "mlx-safetensors", "mlx",
        "local-mlx-isolated-v1", _mlx_evidence("tcn"),
    ),
)

EXPECTED_NAMES = frozenset({
    "lightgbm", "torch-lstm", "torch-tcn", "patchtst", "lnn-ltc", "chronos",
    "mlx-lstm", "mlx-tcn",
})

__all__ = ["EXPECTED_NAMES", "NativePortfolioCase", "PORTFOLIO", "PortfolioEvidence"]
