"""Tests for CDK L2 renderer — validate, render, file generation."""

from __future__ import annotations

import pytest

from factory.blueprint.runtime.renderers.cdk import CdkRenderer, _class_name
from factory.blueprint.runtime.ports import (
    NormalizedResource, InfraBlueprint, IamStatement,
)
from factory.blueprint.core import SERVICE_CDK_MODULES


# ── Helpers ────────────────────────────────────────────────────────

def _res(service: str, brick: str = "store", construct: str = "Table") -> NormalizedResource:
    return NormalizedResource(
        brick=brick, service=service, construct=construct,
        props={}, logical_id=f"{brick}{service}{construct}",
    )


def _blueprint(resources=None, vpc=False) -> InfraBlueprint:
    resources = resources or []
    services = {r.service for r in resources}
    return InfraBlueprint(
        resources=resources, vpc_required=vpc, services_used=services,
    )


@pytest.fixture
def renderer():
    return CdkRenderer()


# ── Validate ───────────────────────────────────────────────────────

class TestValidate:
    def test_no_errors_for_known_service(self, renderer):
        bp = _blueprint([_res("dynamodb")])
        assert renderer.validate(bp) == []

    def test_error_for_unknown_service(self, renderer):
        bp = _blueprint([_res("unknown-svc")])
        errors = renderer.validate(bp)
        assert len(errors) == 1
        assert "unknown-svc" in errors[0]

    def test_empty_blueprint_valid(self, renderer):
        assert renderer.validate(_blueprint()) == []

    def test_mixed_known_unknown(self, renderer):
        bp = _blueprint([_res("dynamodb"), _res("fake")])
        errors = renderer.validate(bp)
        assert len(errors) == 1

    def test_renderer_type(self, renderer):
        assert renderer.renderer_type == "cdk"


# ── Render ─────────────────────────────────────────────────────────

class TestRender:
    def test_generates_app_py(self, renderer):
        bp = _blueprint([_res("dynamodb")])
        out = renderer.render(bp, "myproj")
        assert "cdk/app.py" in out.files

    def test_generates_cdk_json(self, renderer):
        bp = _blueprint([_res("dynamodb")])
        out = renderer.render(bp, "myproj")
        assert "cdk/cdk.json" in out.files
        assert "app.py" in out.files["cdk/cdk.json"]

    def test_generates_requirements(self, renderer):
        bp = _blueprint([_res("dynamodb")])
        out = renderer.render(bp, "myproj")
        assert "cdk/requirements.txt" in out.files
        assert "aws-cdk-lib" in out.files["cdk/requirements.txt"]

    def test_generates_stack_per_brick(self, renderer):
        bp = _blueprint([_res("dynamodb", brick="cache"), _res("s3", brick="storage")])
        out = renderer.render(bp, "proj")
        assert "cdk/stacks/cache_stack.py" in out.files
        assert "cdk/stacks/storage_stack.py" in out.files

    def test_stack_has_class(self, renderer):
        bp = _blueprint([_res("dynamodb", brick="cache")])
        out = renderer.render(bp, "proj")
        content = out.files["cdk/stacks/cache_stack.py"]
        assert "class CacheStack(cdk.Stack):" in content

    def test_entry_point(self, renderer):
        bp = _blueprint([_res("s3")])
        out = renderer.render(bp, "proj")
        assert out.entry_point == "cdk/app.py"

    def test_metadata_has_stacks(self, renderer):
        bp = _blueprint([_res("s3", brick="store")])
        out = renderer.render(bp, "proj")
        assert "store_stack" in out.metadata["stacks"]

    def test_stacks_init_file(self, renderer):
        bp = _blueprint([_res("s3")])
        out = renderer.render(bp, "proj")
        assert "cdk/stacks/__init__.py" in out.files


# ── VPC / Network Stack ───────────────────────────────────────────

class TestNetworkStack:
    def test_no_network_stack_without_vpc(self, renderer):
        bp = _blueprint([_res("dynamodb")])
        out = renderer.render(bp, "proj")
        assert "cdk/stacks/network_stack.py" not in out.files

    def test_network_stack_with_vpc(self, renderer):
        bp = _blueprint([_res("neptune")], vpc=True)
        out = renderer.render(bp, "proj")
        assert "cdk/stacks/network_stack.py" in out.files
        assert "Vpc" in out.files["cdk/stacks/network_stack.py"]

    def test_network_stack_first_in_metadata(self, renderer):
        bp = _blueprint([_res("neptune", construct="DatabaseCluster")], vpc=True)
        out = renderer.render(bp, "proj")
        assert out.metadata["stacks"][0] == "network_stack"


# ── Props Rendering ────────────────────────────────────────────────

class TestPropsRendering:
    def test_string_prop_quoted(self, renderer):
        r = _res("dynamodb")
        r.props = {"table_name": "users"}
        bp = _blueprint([r])
        out = renderer.render(bp, "proj")
        stack = out.files["cdk/stacks/store_stack.py"]
        assert '"users"' in stack

    def test_bool_prop(self, renderer):
        r = _res("dynamodb")
        r.props = {"stream": True}
        bp = _blueprint([r])
        out = renderer.render(bp, "proj")
        stack = out.files["cdk/stacks/store_stack.py"]
        assert "True" in stack

    def test_empty_props(self, renderer):
        bp = _blueprint([_res("s3")])
        out = renderer.render(bp, "proj")
        assert "cdk/stacks/store_stack.py" in out.files


# ── Utility ────────────────────────────────────────────────────────

class TestClassName:
    def test_snake_to_pascal(self):
        assert _class_name("cache_stack") == "CacheStack"

    def test_single_word(self):
        assert _class_name("network") == "Network"
