"""
Property tests for CFN generators and build_cfn_template.

Verifies:
- Each generator returns a single-key dict with valid CFN structure
- Logical IDs have no dots or hyphens
- Type-specific properties (Lambda, KMS, Secret, SSM)
- build_cfn_template assembles correct resource counts
- Unknown types and empty entries are silently skipped
- DynamoDBTable backward-compat alias matches DynamoDB output
"""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from factory.sandbox.runtime.cfn_generators import EXTENDED_GENERATORS
from factory.sandbox.runtime.cfn_defaults import build_cfn_template, _GENERATORS

# Strategy: names that include dots and hyphens (the chars generators strip)
_names = st.text(
    min_size=1,
    max_size=60,
    alphabet=st.characters(
        whitelist_categories=("L", "N"), whitelist_characters="-."
    ),
)


# ── 1. Individual generator properties ───────────────────────────────


class TestExtendedGeneratorStructure:
    """Every generator returns a well-formed CFN resource dict."""

    @settings(max_examples=50)
    @given(name=_names)
    def test_single_key_returned(self, name: str) -> None:
        """Each generator returns exactly one logical-id key."""
        for label, gen in EXTENDED_GENERATORS.items():
            result = gen(name)
            assert len(result) == 1, f"{label} returned {len(result)} keys"

    @settings(max_examples=50)
    @given(name=_names)
    def test_logical_id_has_no_dots_or_hyphens(self, name: str) -> None:
        """Logical IDs must strip dots and hyphens."""
        for label, gen in EXTENDED_GENERATORS.items():
            logical_id = next(iter(gen(name)))
            assert "." not in logical_id, f"{label}: dot in {logical_id}"
            assert "-" not in logical_id, f"{label}: hyphen in {logical_id}"

    @settings(max_examples=50)
    @given(name=_names)
    def test_type_starts_with_aws(self, name: str) -> None:
        """CFN Type must start with 'AWS::'."""
        for label, gen in EXTENDED_GENERATORS.items():
            res = next(iter(gen(name).values()))
            assert res["Type"].startswith("AWS::"), f"{label}: {res['Type']}"

    @settings(max_examples=50)
    @given(name=_names)
    def test_properties_dict_present(self, name: str) -> None:
        """Every CFN resource must have a Properties dict."""
        for label, gen in EXTENDED_GENERATORS.items():
            res = next(iter(gen(name).values()))
            assert isinstance(res["Properties"], dict), label


class TestTypeSpecificProperties:
    """Type-specific required keys in Properties."""

    @settings(max_examples=50)
    @given(name=_names)
    def test_lambda_has_runtime_handler_code(self, name: str) -> None:
        props = next(iter(EXTENDED_GENERATORS["Lambda"](name).values()))["Properties"]
        for key in ("Runtime", "Handler", "Code"):
            assert key in props, f"Lambda missing {key}"

    @settings(max_examples=50)
    @given(name=_names)
    def test_kms_has_key_policy(self, name: str) -> None:
        props = next(iter(EXTENDED_GENERATORS["KMS"](name).values()))["Properties"]
        assert "KeyPolicy" in props

    @settings(max_examples=50)
    @given(name=_names)
    def test_secret_has_secret_string(self, name: str) -> None:
        props = next(iter(EXTENDED_GENERATORS["Secret"](name).values()))["Properties"]
        assert "SecretString" in props

    @settings(max_examples=50)
    @given(name=_names)
    def test_ssm_has_type_and_value(self, name: str) -> None:
        props = next(iter(
            EXTENDED_GENERATORS["SSMParameter"](name).values()
        ))["Properties"]
        assert "Type" in props
        assert "Value" in props


# ── 2. build_cfn_template properties ─────────────────────────────────

_ALL_TYPES = [t for t in _GENERATORS if t != "DynamoDBTable"]
_resource_type = st.sampled_from(_ALL_TYPES)
_resource = st.fixed_dictionaries({"type": _resource_type, "name": _names})


class TestBuildCfnTemplate:
    """Property tests for the template assembler."""

    @settings(max_examples=50)
    @given(resources=st.lists(_resource, min_size=0, max_size=15))
    def test_resource_count_matches_unique_logical_ids(self, resources: list) -> None:
        """Output count equals number of distinct logical IDs from input."""
        tpl = build_cfn_template(resources)
        # Each generator strips dots/hyphens and truncates to get logical ID
        expected_ids = set()
        for r in resources:
            gen = _GENERATORS.get(r["type"])
            if gen and r["name"]:
                lid = next(iter(gen(r["name"])))
                expected_ids.add(lid)
        assert len(tpl["Resources"]) == len(expected_ids)

    @settings(max_examples=50)
    @given(
        name=_names,
        unknown=st.text(min_size=1, max_size=20).filter(
            lambda t: t not in _GENERATORS
        ),
    )
    def test_unknown_types_skipped(self, name: str, unknown: str) -> None:
        """Resources with unrecognised types produce no output."""
        tpl = build_cfn_template([{"type": unknown, "name": name}])
        assert len(tpl["Resources"]) == 0

    @settings(max_examples=50)
    @given(name=_names)
    def test_empty_name_skipped(self, name: str) -> None:
        tpl = build_cfn_template([{"type": "S3", "name": ""}])
        assert len(tpl["Resources"]) == 0

    @settings(max_examples=50)
    @given(name=_names)
    def test_empty_type_skipped(self, name: str) -> None:
        tpl = build_cfn_template([{"type": "", "name": name}])
        assert len(tpl["Resources"]) == 0

    def test_dynamodbtable_alias_matches_dynamodb(self) -> None:
        """Backward-compat alias produces identical output."""
        name = "MyTable"
        a = build_cfn_template([{"type": "DynamoDB", "name": name}])
        b = build_cfn_template([{"type": "DynamoDBTable", "name": name}])
        assert a["Resources"] == b["Resources"]
