"""CAN taxonomize stage and canonical provenance tests."""
from __future__ import annotations

from typing import Any

import pytest

from factory.dataset.runtime.adapters.can_taxonomize import (
    CanTaxonomizeStageAdapter,
)


class _Sentinel: ...


USE_DEFAULT = _Sentinel()


class FakeGraph:
    """Minimal in-memory graph that records all mutations."""

    def __init__(self):
        self.entities = {}
        self.relationships = []
        self._rel_index = set()

    def add_entity(self, e):
        self.entities[e.id] = {"type": e.type,
            "properties": dict(e.properties or {})}
        return e

    def add_relationship(self, r):
        key = (r.source_id, r.type, r.target_id)
        if key in self._rel_index:
            return r
        self._rel_index.add(key)
        self.relationships.append({
            "id": r.id, "type": r.type,
            "source_id": r.source_id, "target_id": r.target_id,
            "properties": dict(r.properties or {})})
        return r


def _record(
    *, vehicle_id="V001", trip_id="T042", bus_name="CAN1",
    timestamp_ns=1_700_000_000_000_000_000, arbitration_id="0x2C1",
    source_ecu="ECM", decoded=USE_DEFAULT,
):
    decoded_payload = (decoded if decoded is not USE_DEFAULT
                       else {"coolant_temp": 80.0, "rpm": 1500.0})
    digest = "a" * 64
    definitions = [{
        "name": name, "unit": "", "minimum": 0.0, "maximum": 10_000.0,
        "scale": 1.0, "offset": 0.0, "length_bits": 16,
        "byte_order": "little_endian",
    } for name in (decoded_payload or {})]
    provenance = {
        "source_url": "file:///tmp/test.dbc", "artifact_uri": "file:///tmp/test.dbc",
        "source_kind": "explicit_local", "spdx_license": "NOASSERTION",
        "retrieved_at": "1970-01-01T00:00:00Z", "sha256": digest,
        "parser_name": "cantools", "parser_version": "test",
        "validation_status": "validated",
    }
    return {"timestamp_ns": timestamp_ns, "vehicle_id": vehicle_id,
        "trip_id": trip_id, "bus_name": bus_name,
        "arbitration_id": arbitration_id, "is_extended": False,
        "is_fd": False, "dlc": 8, "data_bytes": "00" * 8,
        "frame_type": "data", "error_state": "normal",
        "source_ecu": source_ecu, "capture_source": "mf4",
        "decoded_signals": decoded_payload, "dbc_message_name": "ENG1S01",
        "dbc_definition_id": f"dbc-{digest}", "dbc_catalog_id": "test-dbc",
        "dbc_version": "local", "dbc_digest": digest,
        "dbc_provenance": provenance,
        "decoded_signal_definitions": definitions}


def _run(records, *, config=None):
    g = FakeGraph()
    out = list(CanTaxonomizeStageAdapter(graph=g).execute(records, config or {}))
    return out, g


def _ents(g, t): return {k: v for k, v in g.entities.items() if v["type"] == t}
def _rels(g, t): return [r for r in g.relationships if r["type"] == t]


def test_satisfies_dataset_stage_port_surface():
    a = CanTaxonomizeStageAdapter()
    assert a.name == "can_taxonomize"
    assert a.stage_version.startswith("factory-can-taxonomize")
    assert "enable_taxonomy" in a.allowed_config
    assert callable(a.execute)


def test_rejects_unknown_config_keys():
    with pytest.raises(ValueError, match="Unsupported can_taxonomize"):
        list(CanTaxonomizeStageAdapter().execute([], {"rogue_key": True}))


def test_empty_input_yields_empty_output():
    out, g = _run([])
    assert out == [] and g.entities == {} and g.relationships == []


def test_disabled_taxonomy_is_pure_passthrough():
    out, g = _run([_record()], config={"enable_taxonomy": False})
    assert len(out) == 1
    assert out[0]["taxonomy_node_ids"] == [] and out[0]["vehicle_id"] == "V001"
    assert g.entities == {} and g.relationships == []


# --- Entity creation ---------------------------------------------------


def test_creates_one_vehicle_per_unique_id():
    out, g = _run([_record(timestamp_ns=1_700_000_000_000_000_000 + i)
                   for i in range(3)])
    assert len(out) == 3
    v = _ents(g, "Vehicle")
    assert len(v) == 1 and v["vehicle-V001"]["properties"]["vehicle_id"] == "V001"


def test_creates_trip_canbus_frame_per_record_value():
    _, g = _run([_record()])
    types = {e["type"] for e in g.entities.values()}
    assert {"Vehicle", "Trip", "CANBus", "Frame"}.issubset(types)
    assert "trip-V001-T042" in g.entities
    assert "canbus-V001-CAN1" in g.entities
    assert any(eid.startswith("frame-") for eid in g.entities)


def test_creates_ecu_only_when_source_ecu_present():
    _, g = _run([_record(source_ecu="ECM"),
                 _record(timestamp_ns=2, source_ecu=None)])
    assert list(_ents(g, "ECU")) == ["ecu-V001-ECM"]


def test_signal_creation_and_none_decoded():
    """One record with decoded signals creates 2 Signal entities;
    one with decoded=None creates zero."""
    _, g_decoded = _run([_record()])
    signals = _ents(g_decoded, "Signal")
    assert {item["properties"]["signal_name"] for item in signals.values()} == {
        "coolant_temp", "rpm",
    }
    assert all(identity.startswith("signal-") for identity in signals)
    _, g_none = _run([_record(decoded=None)])
    assert _ents(g_none, "Signal") == {}


# --- Relationships -----------------------------------------------------


@pytest.mark.parametrize("rel_type,src,tgt", [
    ("HAS_ECU", "vehicle-V001", "ecu-V001-ECM"),
    ("PART_OF_TRIP", "frame", "trip-V001-T042"),
    ("EMITS_FRAME", "ecu-V001-ECM", "frame"),
])
def test_one_to_one_relationship(rel_type, src, tgt):
    """Source/target endpoints are exact (Vehicle/ECU/Trip) or frame-prefixed."""
    _, g = _run([_record()])
    rels = _rels(g, rel_type)
    assert len(rels) == 1
    s, t = rels[0]["source_id"], rels[0]["target_id"]
    assert s.startswith("frame-") if src == "frame" else s == src
    assert t.startswith("frame-") if tgt == "frame" else t == tgt


def test_has_ecu_includes_bus_name_property():
    _, g = _run([_record()])
    assert _rels(g, "HAS_ECU")[0]["properties"]["bus_name"] == "CAN1"


def test_frame_decodes_to_canonical_signal_relationship():
    _, g = _run([_record()])
    rels = _rels(g, "DECODES_TO")
    assert len(rels) == 2
    assert len({r["source_id"] for r in rels}) == 1
    assert all(r["source_id"].startswith("frame-") for r in rels)
    assert all(r["target_id"].startswith("signal-") for r in rels)
    assert all(r["properties"]["dbc_digest"] for r in rels)


# --- Batching & tagging ------------------------------------------------


def test_records_are_tagged_with_sorted_taxonomy_node_ids():
    out, _ = _run([_record()])
    ids = out[0]["taxonomy_node_ids"]
    assert ids == sorted(ids) and len(ids) == 8


def test_batch_writes_avoid_duplicate_entities():
    """Five records with the same vehicle produce ONE Vehicle entity
    and ONE HAS_ECU edge (dedupe proves the batched write path)."""
    _, g = _run([_record(timestamp_ns=i + 1) for i in range(5)])
    assert len(_ents(g, "Vehicle")) == 1
    assert len(_rels(g, "HAS_ECU")) == 1
