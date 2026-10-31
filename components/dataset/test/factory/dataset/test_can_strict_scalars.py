"""Strict CAN/DBC scalar contracts at Pydantic and progressive MCP boundaries."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from factory.dataset.runtime.can_terminal_models import CanTerminalRequest
from factory.dataset.runtime.dbc_models import MessageFingerprint, VehicleAliases
from factory.dataset.runtime.dbc_semantics import DbcMessageDefinition

from .can_intelligence_fixtures import write_catalog
from .can_mcp_harness import ProgressiveCanHarness


def test_pydantic_can_identifiers_and_vehicle_years_reject_strings() -> None:
    with pytest.raises(ValidationError):
        MessageFingerprint(arbitration_id=1, dlc=8, is_extended="false")
    with pytest.raises(ValidationError):
        VehicleAliases(aliases=("car",), years=("2026",))
    with pytest.raises(ValidationError):
        CanTerminalRequest(attempt_id="strict", mf4_dir="/captures", vehicle_year="2026")
    with pytest.raises(ValidationError):
        DbcMessageDefinition(
            message_id="message-1", name="Message", arbitration_id=1,
            is_extended="false", dlc=8,
        )


def test_progressive_mcp_rejects_coercive_vehicle_and_ide_scalars(tmp_path: Path) -> None:
    _, entry = write_catalog(tmp_path)
    with ProgressiveCanHarness(tmp_path) as mcp:
        year = mcp.dispatch("dataset", "dataset_resolve_dbc_candidate", {
            "vehicle_year": "2026",
        })
        assert year["ok"] is False
        terminal_year = mcp.dispatch(
            "dataset", "dataset_materialize_can_training_bundle",
            {"attempt_id": "strict", "mf4_dir": str(tmp_path),
             "vehicle_year": "2026"},
        )
        assert terminal_year["ok"] is False
        fingerprints = [dict(item) for item in entry["message_fingerprints"]]
        fingerprints[0]["is_extended"] = "false"
        ide = mcp.dispatch("dataset", "dataset_resolve_dbc_candidate", {
            "message_fingerprints": fingerprints,
        })
        assert ide["ok"] is False
