"""Production MCP authority for exact promoted Chronos-2 passports."""
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("chronos", reason="Chronos tests require the ml group")
pytest.importorskip("peft", reason="Chronos tests require the ml group")

from factory.machine_learning.runtime.passport_composition import create_local_passport_service
from factory.machine_learning.runtime.ports import TimeSeriesModelType
from factory.machine_learning.runtime.runtime import TrackingRuntime
from factory.mcp_utils.interface import get_service, set_service

from .test_neural_passport_mcp import _invoke, _tool
from .test_neural_passport_subprocess import _candidate


@pytest.mark.parametrize("lora", [False, True])
def test_mcp_chronos_exact_promoted_ref_has_no_timing(
    tmp_path: Path, lora: bool,
) -> None:
    previous = get_service("tool_invoker")
    try:
        root, _, publication, _, warm = _candidate(
            tmp_path, TimeSeriesModelType.chronos, lora=lora,
        )
        service = create_local_passport_service(root)
        ref = service.verify_and_promote(publication.ref).ref
        runtime = TrackingRuntime(passport_service=service)
        result = _invoke(_tool(runtime, service), ref, str(root / "scoring-X.npy"))
        assert result.ok and result.data is not None
        assert result.data.status == "completed" and result.data.live_timing is None
        tolerance = service.get(ref).architecture.config["parity_tolerance"]
        np.testing.assert_allclose(
            np.asarray(result.data.y_score), warm,
            rtol=tolerance["rtol"], atol=tolerance["atol"],
        )
        assert runtime._inference_registry == {} and runtime._inference_bridges == {}
    finally:
        set_service("tool_invoker", previous)
