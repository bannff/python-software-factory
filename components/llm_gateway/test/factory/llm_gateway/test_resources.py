"""Safety and schema tests for native LLM Gateway resources."""
from unittest.mock import MagicMock

from factory.llm_gateway.mcp.resources import (
    config_schema,
    response_schema,
    safe_health_projection,
)


def test_health_projection_swallows_provider_exception_text() -> None:
    runtime = MagicMock()
    runtime.health_check.side_effect = RuntimeError("api_key=secret endpoint=https://private")

    projection = safe_health_projection(runtime)

    assert projection == {"providers": {}, "all_healthy": False}
    assert "secret" not in str(projection)


def test_response_resource_describes_tool_result_envelope() -> None:
    schema = response_schema()
    assert set(schema["required"]) == {"schema_version", "ok", "data", "error", "idempotency_key"}
    assert schema["properties"]["schema_version"] == {"const": "v1"}


def test_config_resource_exposes_no_credential_or_transport_fields() -> None:
    schema = config_schema()
    assert set(schema["properties"]) == {"backend", "model"}
    assert schema["additionalProperties"] is False
