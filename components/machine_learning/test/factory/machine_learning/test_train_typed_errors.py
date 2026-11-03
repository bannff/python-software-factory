from __future__ import annotations

import asyncio

import pytest

from factory.machine_learning.runtime.runtime import TrackingRuntime
from factory.machine_learning.server import create_tool_catalog


@pytest.fixture
def tools():
    catalog = create_tool_catalog(TrackingRuntime())
    return {t.name: t.fn for t in asyncio.run(catalog.list_tools())}


def test_capabilities_list_the_supported_model_types(tools) -> None:
    types = tools["ml_get_capabilities"]().data.timeseries_model_types
    assert {"lightgbm", "lstm", "tcn"} <= set(types)


def test_train_failures_are_typed(tools, tmp_path) -> None:
    train = tools["ml_train_timeseries"]
    assert train(model_type="nope", X_uri="x.npy", y_uri="y.npy").error == "timeseries_model_type_invalid"
    assert train(model_type="lightgbm", X_uri=str(tmp_path / "missing.npy"),
                 y_uri=str(tmp_path / "missing_y.npy")).error in {
        "training_data_unreadable", "training_failed", "model_root_not_configured", "native_dependency_missing",
    }
    bad_config = train(model_type="lightgbm", X_uri="x.npy", y_uri="y.npy", config={"not_a_field": 1})
    assert not bad_config.ok and "not_a_field" in bad_config.error
