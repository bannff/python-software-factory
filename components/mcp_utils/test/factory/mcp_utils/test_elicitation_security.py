"""Security policy canaries for non-sensitive form elicitation."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr

from factory.mcp_utils.runtime.elicitation import ElicitationForm, ElicitationFormRequest


class SensitiveDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    api_token: str


class NullableSecretDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answer: SecretStr | None = None


def test_elicitation_form_rejects_sensitive_model_fields() -> None:
    with pytest.raises(ValueError, match="sensitive fields"):
        ElicitationFormRequest("Invalid secret form", SensitiveDTO)


@pytest.mark.parametrize("field", [
    "otp", "otpCode", "totpCode", "hotpCode", "pin", "pinCode",
    "passcode", "authorization_code", "authorizationCode",
    "verification_code", "recovery_code", "bearerValue", "jwtValue",
    "mfaCode", "csrfValue", "session_cookie", "security_answer",
])
def test_elicitation_form_rejects_authentication_factors(field: str) -> None:
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {field: {"type": "string"}}, "required": [field],
    }
    with pytest.raises(ValueError, match="sensitive fields"):
        ElicitationForm("Authentication factors are not allowed", schema)


@pytest.mark.parametrize("field_format", ["Password", "SECRET"])
def test_elicitation_form_rejects_case_variant_secret_formats(
    field_format: str,
) -> None:
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"answer": {"type": "string", "format": field_format}},
    }
    with pytest.raises(ValueError, match="sensitive fields"):
        ElicitationForm("Secret formats are not allowed", schema)


def test_elicitation_form_rejects_nullable_secret_model() -> None:
    with pytest.raises(ValueError, match="sensitive fields"):
        ElicitationFormRequest("Nullable secret", NullableSecretDTO)


def test_elicitation_form_rejects_arbitrary_text_collection() -> None:
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"answer": {"type": "string"}},
    }
    with pytest.raises(ValueError, match="2..8 option enum"):
        ElicitationForm("Only confirmation is supported", schema)


def test_elicitation_form_rejects_unsupported_field_types() -> None:
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"answer": {"type": "integer"}},
        "required": ["answer"],
    }
    with pytest.raises(ValueError, match="must be boolean or a string enum"):
        ElicitationForm("Only confirmation is supported", schema)


def test_elicitation_form_accepts_bounded_string_enum() -> None:
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"answer": {"type": "string", "enum": ["yes", "no", "maybe"]}},
        "required": ["answer"],
    }
    ElicitationForm("Pick one", schema)


def test_elicitation_form_rejects_single_option_enum() -> None:
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"answer": {"type": "string", "enum": ["only"]}},
        "required": ["answer"],
    }
    with pytest.raises(ValueError, match="2..8 option enum"):
        ElicitationForm("Pick one", schema)


def test_elicitation_form_rejects_oversized_enum() -> None:
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"answer": {"type": "string", "enum": [str(i) for i in range(9)]}},
        "required": ["answer"],
    }
    with pytest.raises(ValueError, match="2..8 option enum"):
        ElicitationForm("Pick one", schema)


def test_elicitation_form_rejects_empty_enum_option() -> None:
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"answer": {"type": "string", "enum": ["ok", ""]}},
        "required": ["answer"],
    }
    with pytest.raises(ValueError, match="non-empty strings"):
        ElicitationForm("Pick one", schema)
