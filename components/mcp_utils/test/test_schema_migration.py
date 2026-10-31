"""Tests for the central schema-migration dispatcher."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import BaseModel, Field

from factory.mcp_utils.runtime.schema_migration import (
    SchemaMigrationError,
    clear_steps,
    migrate_to,
    register_step,
)


class _V2Model(BaseModel):
    schema_version: Literal["v2"] = "v2"
    doc_id: str
    content: str


def _v1_to_v2(data: dict) -> dict:
    return {
        "schema_version": "v2",
        "doc_id": data["doc_id"],
        "content": data["body"],
    }


@pytest.fixture(autouse=True)
def _clear_steps():
    clear_steps()
    yield
    clear_steps()


class TestMigrateForward:
    def test_already_current_no_migration(self) -> None:
        v2 = {"schema_version": "v2", "doc_id": "x", "content": "y"}
        result = migrate_to(v2, _V2Model)
        assert result.doc_id == "x"
        assert result.content == "y"
        assert result.schema_version == "v2"

    def test_v1_missing_version_field_walks_forward(self) -> None:
        register_step("_V2Model", "v1", _v1_to_v2)
        v1 = {"doc_id": "x", "body": "y"}
        result = migrate_to(v1, _V2Model)
        assert result.doc_id == "x"
        assert result.content == "y"
        assert result.schema_version == "v2"

    def test_idempotency_under_repeated_migration(self) -> None:
        register_step("_V2Model", "v1", _v1_to_v2)
        v1 = {"doc_id": "x", "body": "y"}
        a = migrate_to(v1, _V2Model)
        b = migrate_to(v1, _V2Model)
        assert a.model_dump() == b.model_dump()

    def test_missing_path_raises(self) -> None:
        v99 = {"schema_version": "v99", "doc_id": "x", "content": "y"}
        with pytest.raises(SchemaMigrationError, match="No migration path"):
            migrate_to(v99, _V2Model)

    def test_no_migration_registered_for_current_model_returns_immediately(self) -> None:
        result = migrate_to(
            {"schema_version": "v2", "doc_id": "x", "content": "y"},
            _V2Model,
        )
        assert result.doc_id == "x"


class TestRegisterStep:
    def test_re_register_replaces(self) -> None:
        def step_a(data: dict) -> dict:
            return {
                "schema_version": "v2",
                "doc_id": "A",
                "content": data["body"],
            }

        def step_b(data: dict) -> dict:
            return {
                "schema_version": "v2",
                "doc_id": "B",
                "content": data["body"],
            }

        register_step("_V2Model", "v1", step_a)
        register_step("_V2Model", "v1", step_b)
        result = migrate_to({"doc_id": "?", "body": "y"}, _V2Model)
        assert result.doc_id == "B"

    def test_clear_steps_isolates_tests(self) -> None:
        """The autouse fixture clears _STEP between tests."""
        register_step("_V2Model", "v1", _v1_to_v2)
        from factory.mcp_utils.runtime.schema_migration import _STEP

        assert ("_V2Model", "v1") in _STEP
        # After this test exits, the fixture clears _STEP again.


class TestErrorSurface:
    @pytest.mark.parametrize("version", [1, None, {"version": "v1"}])
    def test_non_string_schema_version_has_stable_error(self, version: object) -> None:
        with pytest.raises(SchemaMigrationError, match="schema_version must be a string"):
            migrate_to(
                {"schema_version": version, "doc_id": "x", "content": "y"},
                _V2Model,
            )

    def test_validation_error_after_migration_raises_schemamigrationerror(self) -> None:
        class _StrictV3(BaseModel):
            schema_version: Literal["v3"] = "v3"
            doc_id: str = Field(..., min_length=5)

        def v1_to_v3(data: dict) -> dict:
            return {"schema_version": "v3", "doc_id": data.get("doc_id", "")}

        register_step("_StrictV3", "v1", v1_to_v3)
        with pytest.raises(SchemaMigrationError, match="validation failed"):
            migrate_to({"doc_id": "ab"}, _StrictV3)


class TestLegacyCallers:
    def test_no_version_field_defaults_to_v1(self) -> None:
        """Legacy callers (pre-versioning) omit schema_version entirely.

        They default to v1 and walk forward from there.
        """
        register_step("_V2Model", "v1", _v1_to_v2)
        legacy = {"doc_id": "x", "body": "y"}
        result = migrate_to(legacy, _V2Model)
        assert result.content == "y"

    def test_model_without_version_field_passes_through(self) -> None:
        class _NoVersion(BaseModel):
            name: str

        result = migrate_to({"name": "alice"}, _NoVersion)
        assert result.name == "alice"


class TestStepReturnType:
    def test_step_must_return_dict(self) -> None:
        """Defense in depth: a step returning a non-dict is a programming error."""
        register_step("_V2Model", "v1", lambda data: "not a dict")
        with pytest.raises(SchemaMigrationError, match="returned str"):
            migrate_to({"doc_id": "x", "body": "y"}, _V2Model)


class TestMultiHop:
    def test_v1_to_v2_to_v3_chain(self) -> None:
        """Multiple registered steps are walked in order."""

        class _V3Model(BaseModel):
            schema_version: Literal["v3"] = "v3"
            doc_id: str
            content: str
            author: str

        def v1_to_v2(data: dict) -> dict:
            return {
                "schema_version": "v2",
                "doc_id": data["doc_id"],
                "content": data["body"],
            }

        def v2_to_v3(data: dict) -> dict:
            return {
                "schema_version": "v3",
                "doc_id": data["doc_id"],
                "content": data["content"],
                "author": "anonymous",
            }

        register_step("_V3Model", "v1", v1_to_v2)
        register_step("_V3Model", "v2", v2_to_v3)
        result = migrate_to(
            {"doc_id": "x", "body": "hello"}, _V3Model
        )
        assert result.doc_id == "x"
        assert result.content == "hello"
        assert result.author == "anonymous"
        assert result.schema_version == "v3"
