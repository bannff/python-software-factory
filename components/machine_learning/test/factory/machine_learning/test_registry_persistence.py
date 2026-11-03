from __future__ import annotations

from factory.machine_learning.runtime.dataset_registry import DatasetRecord, DatasetRegistry
from factory.machine_learning.runtime.persistent_dict import PersistentDict, registry_dir


def test_values_survive_a_restart_and_deletes_stick() -> None:
    first = PersistentDict("base_models")
    first["b1"] = {"name": "b1", "model_id": "org/m"}
    first["b2"] = {"name": "b2", "model_id": "org/n"}
    del first["b2"]
    restarted = PersistentDict("base_models")
    assert dict(restarted) == {"b1": {"name": "b1", "model_id": "org/m"}}


def test_datasets_survive_a_restart_with_their_revision() -> None:
    reg = DatasetRegistry()
    reg.register(DatasetRecord("d1", "s3://b/d", "s3://b/m", "sha256:" + "a" * 64, "v", "1", "first"))
    reg.update("d1", 1, "edited")
    again = DatasetRegistry()
    record = again.get("d1")
    assert record.description == "edited" and record.revision == 2


def test_a_damaged_file_does_not_stop_startup() -> None:
    registry_dir().mkdir(parents=True, exist_ok=True)
    (registry_dir() / "base_models.json").write_text("{not json")
    assert dict(PersistentDict("base_models")) == {}
    broken = PersistentDict("base_models")
    broken["ok"] = {"name": "ok"}
    assert dict(PersistentDict("base_models")) == {"ok": {"name": "ok"}}
