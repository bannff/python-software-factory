"""Progressive named-MCP acceptance for Dataset CAN intelligence and Graph."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .can_intelligence_fixtures import write_catalog, write_probe_mf4
from .can_mcp_harness import MINIMAL_DBC, ProgressiveCanHarness, materialize, rows


def _graph_data(result: dict) -> dict:
    """Assert Graph's typed egress contract and return its payload."""
    assert result["schema_version"] == "v1"
    assert result["ok"] is True
    assert result["error"] is None
    assert isinstance(result["data"], dict)
    return result["data"]


def test_progressive_mf4_pattern_artifacts_and_graph_readback(tmp_path: Path) -> None:
    dbc_path, entry = write_catalog(tmp_path)
    write_probe_mf4(tmp_path)
    with ProgressiveCanHarness(tmp_path) as mcp:
        catalog = mcp.call("dataset", "dataset_query_dbc_catalog")
        assert catalog["count"] == 1
        assert catalog["entries"][0]["artifact_status"] == "verified"
        resolved = mcp.call("dataset", "dataset_resolve_dbc_candidate", {
            "vehicle_make": "Fixture", "vehicle_model": "Car", "vehicle_year": 2026,
            "message_fingerprints": entry["message_fingerprints"],
        })
        assert resolved["status"] == "resolved"
        assert "observed message fingerprints matched: 3/3" \
            in resolved["candidates"][0]["explanation"]

        listed = mcp.call("dataset", "dataset_list_failure_patterns")
        inspected = {
            ref["pattern_id"]: mcp.call("dataset", "dataset_inspect_failure_pattern", {
                "pattern_id": ref["pattern_id"], "version": ref["version"],
            }) for ref in listed["patterns"]
        }
        assert listed["count"] == 3
        assert all(
            source["retrieved_at"] and source["source_digest"]
            and "/08ee9b7f42ac98802990eceda37b883a44e159a6/" in source["source_url"]
            and source["spdx_license"] == "BUSL-1.1"
            for item in inspected.values() for source in item["sources"]
        )
        selected = next(ref for ref in listed["patterns"]
                        if ref["pattern_id"] == "coupled-drift")
        terminal = materialize(mcp, tmp_path, "accepted", [selected])
        assert terminal["status"] == "completed"
        assert terminal["dbc_selection"]["message_fingerprints"] \
            == entry["message_fingerprints"]
        definition = terminal["dbc_definition"]
        assert definition["version"] == "1.0.0"
        assert definition["provenance"] == entry["provenance"]
        pattern_key = terminal["training_bundle"]["failure_pattern_artifacts"]["coupled-drift"]
        pattern_artifact = terminal["artifacts"][pattern_key]
        content = Path(pattern_artifact["uri"].removeprefix("file://")).read_bytes()
        assert hashlib.sha256(content).hexdigest() == pattern_artifact["sha256"]
        synth_uri = terminal["stage_receipts"]["synthesize"]["dataset_uri"]
        generated = rows(synth_uri)
        assert generated and any(row["is_failure"] == 1 for row in generated)
        assert all(row["dbc_provenance"] == entry["provenance"] for row in generated)
        assert all(row["failure_pattern_lineage"][0]["scenario_pack"]["digest"]
                   for row in generated)

        projection = mcp.call("dataset", "dataset_project_can_graph", {
            "dataset_uri": synth_uri, "graph_backend": "networkx",
        })
        assert projection["status"] == "completed"
        assert projection["record_count"] == len(generated)
        dbc = _graph_data(mcp.call("graph", "graph_get_entity", {
            "entity_id": definition["definition_id"], "backend": "networkx",
        }))
        assert dbc["found"] is True
        assert dbc["entity"] is not None
        dbc_properties = dbc["entity"]["properties"]
        assert dbc_properties["dbc_version"] == definition["version"]
        assert dbc_properties["source_uri"] == entry["provenance"]["source_url"]
        assert dbc_properties["spdx_license"] == entry["provenance"]["spdx_license"]
        assert dbc_properties["parser_version"] == entry["provenance"]["parser_version"]
        frames = _graph_data(mcp.call("graph", "graph_find_entities", {
            "entity_type": "Frame", "limit": 1000, "backend": "networkx",
        }))
        assert frames["count"] == len(generated)
        neighbors = _graph_data(mcp.call("graph", "graph_get_neighbors", {
            "entity_id": frames["entities"][0]["id"],
            "relationship_type": "DECODES_TO", "direction": "out",
            "backend": "networkx",
        }))
        assert neighbors["count"]
        assert all(item["type"] == "Signal" for item in neighbors["neighbors"])
        trips = _graph_data(mcp.call("graph", "graph_find_entities", {
            "entity_type": "Trip", "limit": 100, "backend": "networkx",
        }))
        expected_bounds: dict[str, tuple[int, int]] = {}
        for row in generated:
            identity = f"trip-{row['vehicle_id']}-{row['trip_id']}"
            timestamp = int(row["timestamp_ns"])
            start, end = expected_bounds.get(identity, (timestamp, timestamp))
            expected_bounds[identity] = min(start, timestamp), max(end, timestamp)
        observed_bounds = {
            item["id"]: (item["properties"]["start_ts"], item["properties"]["end_ts"])
            for item in trips["entities"]
        }
        assert observed_bounds == expected_bounds

        (tmp_path / "dbc_catalog" / "manifest.json").write_text("not-json")
        explicit = materialize(mcp, tmp_path, "explicit-precedence", [], str(dbc_path))
        assert explicit["status"] == "completed"
        assert explicit["dbc_definition"]["provenance"]["source_kind"] == "explicit_local"
        assert explicit["dbc_definition"]["catalog_id"].startswith("explicit-")


def test_mcp_failures_are_loud_and_server_remains_healthy(tmp_path: Path) -> None:
    with ProgressiveCanHarness(tmp_path) as mcp:
        patterns = mcp.call("dataset", "dataset_list_failure_patterns")["patterns"]
        coupled = next(item for item in patterns if item["pattern_id"] == "coupled-drift")
        response = next(item for item in patterns if item["pattern_id"] == "response-lag")
        correlation = next(item for item in patterns if item["pattern_id"] == "correlation-loss")

        wrong_root = tmp_path / "wrong"
        write_catalog(wrong_root)
        write_probe_mf4(wrong_root)
        wrong = materialize(mcp, wrong_root, "wrong-digest", [
            {**coupled, "digest": "0" * 64},
        ])
        assert wrong["status"] == "failed" and "digest mismatch" in wrong["error"]

        missing_root = tmp_path / "missing"
        write_catalog(missing_root, dbc_text=MINIMAL_DBC, fingerprints=[
            {"arbitration_id": 257, "dlc": 8, "is_extended": False},
        ])
        write_probe_mf4(missing_root)
        missing = materialize(mcp, missing_root, "missing-role", [coupled])
        assert missing["status"] == "failed" and "missing role" in missing["error"]

        noop_root = tmp_path / "noop"
        write_catalog(noop_root)
        write_probe_mf4(noop_root, constant=True)
        noop = materialize(mcp, noop_root, "no-op", [response])
        assert noop["status"] == "failed" and "mutation constraint" in noop["error"]

        absent_root = tmp_path / "absent-correlation"
        write_catalog(absent_root)
        write_probe_mf4(absent_root, constant=True)
        absent = materialize(mcp, absent_root, "absent-correlation", [correlation])
        assert absent["status"] == "failed"
        assert "requires can_profile correlation" in absent["error"]
        assert mcp.call("dataset", "dataset_list_failure_patterns")["count"] == 3
