"""
Property-based tests for CfnProvisioner, ComposeProvisioner, and validate_manifest.

Verified invariants:
1. CfnProvisioner.plan() step count ==
   len(data_stores) + len(cfn-eligible compute) + (1 if cfn_template) + len(init_scripts).
   All steps start as "pending".
2. ComposeProvisioner.plan() step count ==
   len(compose-eligible compute) + len(rpc/rest deps).
3. CfnProvisioner.apply() with always-succeed execute_fn:
   resources_created count == steps_completed, errors empty, success=True.
4. CfnProvisioner.apply() with always-fail execute_fn:
   success=False, errors non-empty.
5. validate_manifest(): valid manifests (with at least one resource) → valid=True;
   empty manifests → valid=False.
"""
from __future__ import annotations

import asyncio
from typing import Any

from hypothesis import given, settings, strategies as st

from factory.sandbox.runtime.manifest import (
    ComputeSpec,
    DataStoreSpec,
    SandboxManifest,
    ServiceDepSpec,
)
from factory.sandbox.runtime.adapters.cfn_provisioner import CfnProvisioner
from factory.sandbox.runtime.adapters.compose_provisioner import ComposeProvisioner
from factory.sandbox.runtime.provisioning import validate_manifest


def _run(coro: Any) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    return asyncio.run(coro) if loop is None else loop.run_until_complete(coro)


# -- Strategies ---------------------------------------------------------------

_name = st.text(min_size=1, max_size=20, alphabet=st.characters(
    whitelist_categories=("L", "N")))

_data_stores = st.lists(st.builds(
    DataStoreSpec,
    type=st.sampled_from(["dynamodb", "s3", "sqs", "sns", "kms", "secret", "ssm"]),
    name=_name,
), max_size=5)

_cfn_compute = st.lists(st.builds(
    ComputeSpec, type=st.sampled_from(["lambda", "ecs"]), name=_name,
), max_size=4)

_compose_compute = st.lists(st.builds(
    ComputeSpec, type=st.sampled_from(["java_server", "container"]), name=_name,
), max_size=4)

_all_compute = st.lists(st.builds(
    ComputeSpec,
    type=st.sampled_from(["lambda", "ecs", "java_server", "container"]),
    name=_name,
), max_size=5)

_service_deps = st.lists(st.builds(
    ServiceDepSpec,
    type=st.sampled_from(["rpc", "rest", "graphql"]),
    name=_name,
), max_size=4)

_cfn_template = st.one_of(st.none(), st.text(min_size=1, max_size=100))
_init_scripts = st.lists(st.text(min_size=1, max_size=60), max_size=3)


# -- 1. CfnProvisioner.plan() step count & pending status --------------------

class TestCfnPlanProperties:

    @settings(max_examples=50)
    @given(ds=_data_stores, compute=_all_compute,
           cfn=_cfn_template, scripts=_init_scripts)
    def test_plan_step_count(self, ds, compute, cfn, scripts):
        """Step count == data_stores + cfn-eligible compute + cfn_template + scripts."""
        m = SandboxManifest(app_name="app", data_stores=ds, compute=compute,
                            cfn_template=cfn, init_scripts=scripts)
        plan = _run(CfnProvisioner().plan(m))
        cfn_eligible = [c for c in compute if c.type in ("lambda", "ecs")]
        expected = len(ds) + len(cfn_eligible) + (1 if cfn else 0) + len(scripts)
        assert len(plan.steps) == expected

    @settings(max_examples=50)
    @given(ds=_data_stores, compute=_cfn_compute, scripts=_init_scripts)
    def test_all_steps_start_pending(self, ds, compute, scripts):
        """Every step in a fresh plan has status 'pending'."""
        m = SandboxManifest(app_name="app", data_stores=ds, compute=compute,
                            init_scripts=scripts)
        plan = _run(CfnProvisioner().plan(m))
        assert all(s.status == "pending" for s in plan.steps)


# -- 2. ComposeProvisioner.plan() step count ----------------------------------

class TestComposePlanProperties:

    @settings(max_examples=50)
    @given(compute=_all_compute, deps=_service_deps)
    def test_plan_step_count(self, compute, deps):
        """Steps == compose-eligible compute + rpc/rest deps."""
        m = SandboxManifest(app_name="app", compute=compute, service_deps=deps)
        plan = _run(ComposeProvisioner().plan(m))
        compose_eligible = [c for c in compute
                            if c.type in ("java_server", "container")]
        stub_deps = [d for d in deps if d.type in ("rpc", "rest")]
        assert len(plan.steps) == len(compose_eligible) + len(stub_deps)


# -- 3. CfnProvisioner.apply() — all succeed ---------------------------------

class TestCfnApplySuccessProperties:

    @settings(max_examples=50)
    @given(ds=_data_stores, compute=_cfn_compute, scripts=_init_scripts)
    def test_apply_all_succeed(self, ds, compute, scripts):
        """When execute_fn always succeeds: success=True, no errors,
        resources_created == resource steps (scripts are not resources)."""
        m = SandboxManifest(app_name="app", data_stores=ds, compute=compute,
                            init_scripts=scripts)
        plan = _run(CfnProvisioner().plan(m))
        if not plan.steps:
            return  # nothing to apply

        async def _ok(*_a, **_kw):
            return {"exit_code": 0, "success": True, "stdout": "ok", "stderr": ""}

        result = _run(CfnProvisioner().apply("env-1", plan, _ok))
        assert result.success is True
        assert result.errors == []
        assert result.steps_completed == len(plan.steps)
        resource_steps = [s for s in plan.steps if s.action != "run_script"]
        assert len(result.resources_created) == len(resource_steps)


# -- 4. CfnProvisioner.apply() — all fail ------------------------------------

class TestCfnApplyFailureProperties:

    @settings(max_examples=50)
    @given(ds=_data_stores, compute=_cfn_compute, scripts=_init_scripts)
    def test_apply_all_fail(self, ds, compute, scripts):
        """When execute_fn always fails: success=False, errors non-empty."""
        m = SandboxManifest(app_name="app", data_stores=ds, compute=compute,
                            init_scripts=scripts)
        plan = _run(CfnProvisioner().plan(m))
        if not plan.steps:
            return

        async def _fail(*_a, **_kw):
            return {"exit_code": 1, "success": False, "stdout": "", "stderr": "boom"}

        result = _run(CfnProvisioner().apply("env-1", plan, _fail))
        assert result.success is False
        assert len(result.errors) > 0


# -- 5. validate_manifest() --------------------------------------------------

class TestValidateManifestProperties:

    @settings(max_examples=50)
    @given(ds=_data_stores, compute=_all_compute, cfn=_cfn_template)
    def test_valid_manifest_accepted(self, ds, compute, cfn):
        """Manifests with at least one resource validate as valid=True."""
        if not ds and not compute and not cfn:
            return  # skip empty — tested below
        data = SandboxManifest(app_name="app", data_stores=ds,
                               compute=compute, cfn_template=cfn).model_dump()
        result = _run(validate_manifest(data))
        assert result["valid"] is True
        assert result["errors"] == []

    @settings(max_examples=50)
    @given(app=_name)
    def test_empty_manifest_rejected(self, app):
        """Manifests with no data_stores, compute, or cfn_template are invalid."""
        data = SandboxManifest(app_name=app).model_dump()
        result = _run(validate_manifest(data))
        assert result["valid"] is False
        assert len(result["errors"]) > 0
