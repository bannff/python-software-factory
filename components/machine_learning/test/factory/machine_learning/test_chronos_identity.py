"""Installed Chronos public and implementation identity contracts."""
import pytest

chronos = pytest.importorskip("chronos", reason="Chronos tests require the ml group")
chronos_model = pytest.importorskip("chronos.chronos2.model")
Chronos2Pipeline = chronos.Chronos2Pipeline
Chronos2Model = chronos_model.Chronos2Model

from factory.machine_learning.runtime.adapters.chronos_identity import (
    MODEL_CLASS,
    PIPELINE_CLASS,
    PIPELINE_IMPLEMENTATION_CLASS,
)
from factory.machine_learning.runtime.chronos_acquisition_evidence import (
    acquisition_document,
)
from factory.machine_learning.runtime.adapters.chronos_identity import MODEL_REVISION


def _identity(value: type) -> str:
    return f"{value.__module__}.{value.__name__}"


def test_installed_chronos_identities_match_acquisition_contract() -> None:
    """Bind both the stable public loader name and the concrete SDK type."""
    assert PIPELINE_CLASS == "chronos.Chronos2Pipeline"
    assert _identity(Chronos2Pipeline) == PIPELINE_IMPLEMENTATION_CLASS
    assert _identity(Chronos2Model) == MODEL_CLASS
    evidence = acquisition_document(MODEL_REVISION)
    assert evidence["pipeline_class"] == PIPELINE_CLASS
    assert evidence["pipeline_implementation_class"] == PIPELINE_IMPLEMENTATION_CLASS
