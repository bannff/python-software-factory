"""Keystone validation arrays pass unchanged to the Evals MCP seam."""
from types import SimpleNamespace

from factory.machine_learning.runtime.can_keystone_training import _augment_with_can_eval


def test_keystone_passes_exact_job_validation_arrays_to_evals(monkeypatch) -> None:
    y_true = [0.0, 1.0]
    y_pred = [0.0, 1.0]
    y_score = [0.25, 0.75]
    job = SimpleNamespace(
        val_y_true=y_true, val_y_pred=y_pred, val_y_score=y_score, metrics={},
    )
    received = {}

    def invoke(name, **kwargs):
        received["name"] = name
        received.update(kwargs)
        return SimpleNamespace(
            ok=True,
            data=SimpleNamespace(model_dump=lambda **_kwargs: {"f1": 1.0}),
        )

    monkeypatch.setattr(
        "factory.machine_learning.runtime.can_keystone_helpers._get_invoker",
        lambda: invoke,
    )
    _augment_with_can_eval(None, job, "vehicle")

    assert received["name"] == "evals_evaluate_can_model"
    assert received["y_true"] is y_true
    assert received["y_pred"] is y_pred
    assert received["y_score"] is y_score
    assert job.metrics == {"f1": 1.0}
