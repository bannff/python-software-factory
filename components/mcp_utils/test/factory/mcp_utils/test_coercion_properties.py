"""Hypothesis property tests for mcp_utils JsonObject / JsonArray coercion.

The JsonObject/JsonArray aliases attach a ``BeforeValidator`` that ``json.loads``
a ``str`` input (native dict/list pass through untouched), so LLM-stringified
object/array MCP args auto-recover while malformed strings still fail loudly.
See the evals-level example test (test_run_record_arg_coercion.py) for the
end-to-end tool proof; here we pin the coercion contract directly.

Properties verified:
1. Round-trip equivalence: validate({f: d}) == validate({f: json.dumps(d)}).
2. Native pass-through: a native dict/list validates to equal content and the
   input object is not mutated.
3. Loud failure: a non-JSON string raises pydantic ValidationError.
4. Wrong-type-after-parse: a string that json.loads-es to the wrong container
   (or a scalar) fails the dict/list type check loudly.
5. Empty {} / [] round-trip cleanly through both paths.
"""
from __future__ import annotations

import copy
import json

from hypothesis import assume, given, settings
from hypothesis import strategies as st
from pydantic import BaseModel, ValidationError

from factory.mcp_utils.interface import JsonArray, JsonObject


class ObjModel(BaseModel):
    field: JsonObject


class ArrModel(BaseModel):
    field: JsonArray


# JSON value strategy: finite scalars + nested lists/dicts with string keys so
# that json.loads(json.dumps(x)) == x holds (int keys would coerce to strings).
_scalars = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=20)
)
json_values = st.recursive(
    _scalars,
    lambda children: st.lists(children, max_size=4)
    | st.dictionaries(st.text(max_size=8), children, max_size=4),
    max_leaves=15,
)
json_objects = st.dictionaries(st.text(max_size=8), json_values, max_size=5)
json_arrays = st.lists(json_values, max_size=5)


@given(d=json_objects)
@settings(max_examples=50)
def test_object_string_and_dict_paths_equivalent(d):
    """A stringified object validates identically to the native dict."""
    from_native = ObjModel.model_validate({"field": d}).field
    from_string = ObjModel.model_validate({"field": json.dumps(d)}).field
    assert from_native == from_string == d


@given(items=json_arrays)
@settings(max_examples=50)
def test_array_string_and_list_paths_equivalent(items):
    """A stringified array validates identically to the native list."""
    from_native = ArrModel.model_validate({"field": items}).field
    from_string = ArrModel.model_validate({"field": json.dumps(items)}).field
    assert from_native == from_string == items


@given(d=json_objects)
@settings(max_examples=50)
def test_native_dict_passthrough_not_mutated(d):
    """A native dict passes through unchanged; the input is not mutated."""
    snapshot = copy.deepcopy(d)
    result = ObjModel.model_validate({"field": d}).field
    assert result == snapshot
    assert d == snapshot  # BeforeValidator must not mutate a native object


@given(items=json_arrays)
@settings(max_examples=50)
def test_native_list_passthrough_not_mutated(items):
    """A native list passes through unchanged; the input is not mutated."""
    snapshot = copy.deepcopy(items)
    result = ArrModel.model_validate({"field": items}).field
    assert result == snapshot
    assert items == snapshot


# Strings starting with '}' can never be valid JSON, so json.loads always raises.
malformed_strings = st.text(max_size=40).map(lambda s: "}" + s)


@given(bad=malformed_strings)
@settings(max_examples=50)
def test_malformed_string_fails_loudly_object(bad):
    """A non-JSON string raises ValidationError, never a silent default."""
    try:
        ObjModel.model_validate({"field": bad})
    except ValidationError:
        return
    raise AssertionError("malformed JSON string must raise, not coerce silently")


@given(bad=malformed_strings)
@settings(max_examples=50)
def test_malformed_string_fails_loudly_array(bad):
    try:
        ArrModel.model_validate({"field": bad})
    except ValidationError:
        return
    raise AssertionError("malformed JSON string must raise, not coerce silently")


@given(items=json_arrays)
@settings(max_examples=50)
def test_array_string_into_object_field_rejected(items):
    """A JSON *array* string in a JsonObject field fails the dict type check."""
    try:
        ObjModel.model_validate({"field": json.dumps(items)})
    except ValidationError:
        return
    raise AssertionError("array parsed into an object field must fail loudly")


@given(d=json_objects)
@settings(max_examples=50)
def test_object_string_into_array_field_rejected(d):
    """A JSON *object* string in a JsonArray field fails the list type check."""
    try:
        ArrModel.model_validate({"field": json.dumps(d)})
    except ValidationError:
        return
    raise AssertionError("object parsed into an array field must fail loudly")


@given(scalar=_scalars)
@settings(max_examples=50)
def test_scalar_string_into_object_field_rejected(scalar):
    """A JSON scalar string (e.g. '\"just a string\"', '5') is not a dict."""
    encoded = json.dumps(scalar)
    # Skip the degenerate cases that are themselves valid containers (none here,
    # scalars only) -- guard anyway in case the strategy widens later.
    assume(not isinstance(scalar, (dict, list)))
    try:
        ObjModel.model_validate({"field": encoded})
    except ValidationError:
        return
    raise AssertionError("scalar parsed into an object field must fail loudly")


def test_empty_object_roundtrips_both_paths():
    assert ObjModel.model_validate({"field": {}}).field == {}
    assert ObjModel.model_validate({"field": "{}"}).field == {}


def test_empty_array_roundtrips_both_paths():
    assert ArrModel.model_validate({"field": []}).field == []
    assert ArrModel.model_validate({"field": "[]"}).field == []
