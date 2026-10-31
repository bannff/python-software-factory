"""Tests for GraphQLConnector adapter (gql library).

Tests instantiation, lifecycle, and protocol conformance.
Network calls are mocked since gql would try to reach real endpoints.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from factory.integrations.core import ConnectorStatus
from factory.integrations.runtime.adapters.graphql import GraphQLConnector
from factory.integrations.runtime.models import ConnectorConfig


@pytest.fixture
def config() -> ConnectorConfig:
    return ConnectorConfig(
        id="gh-graphql",
        name="GitHub GraphQL",
        connector_type="graphql",
        base_url="https://api.github.com/graphql",
    )


class TestGraphQLConnector:
    """Tests for GraphQLConnector using gql library."""

    def test_import(self) -> None:
        """GraphQLConnector and gql are importable."""
        from gql import Client
        assert Client is not None
        assert GraphQLConnector is not None

    def test_instantiation(self, config: ConnectorConfig) -> None:
        """Can create a connector."""
        connector = GraphQLConnector(config)
        assert connector.config.id == "gh-graphql"
        assert connector.status == ConnectorStatus.DISCONNECTED

    def test_connect(self, config: ConnectorConfig) -> None:
        """connect() transitions to CONNECTED."""
        connector = GraphQLConnector(config)
        assert connector.connect() is True
        assert connector.is_connected() is True
        assert connector.status == ConnectorStatus.CONNECTED

    def test_disconnect(self, config: ConnectorConfig) -> None:
        """disconnect() transitions to DISCONNECTED."""
        connector = GraphQLConnector(config)
        connector.connect()
        connector.disconnect()
        assert connector.is_connected() is False
        assert connector.status == ConnectorStatus.DISCONNECTED

    def test_call_without_connection(self, config: ConnectorConfig) -> None:
        """call() without connecting returns error."""
        connector = GraphQLConnector(config)
        result = connector.call("POST", "", data={"query": "{ viewer { login } }"})
        assert result.success is False
        assert "Not connected" in result.error

    def test_call_with_mocked_execute(self, config: ConnectorConfig) -> None:
        """call() executes a GraphQL query via gql Client."""
        connector = GraphQLConnector(config)
        connector.connect()

        mock_result = {"viewer": {"login": "testuser"}}
        with patch.object(connector._client, "execute", return_value=mock_result):
            result = connector.call(
                "POST", "",
                data={"query": "{ viewer { login } }"},
            )
        assert result.success is True
        assert result.data == {"viewer": {"login": "testuser"}}
        assert result.status_code == 200

    def test_call_with_variables(self, config: ConnectorConfig) -> None:
        """call() passes variables to gql execute."""
        connector = GraphQLConnector(config)
        connector.connect()

        with patch.object(connector._client, "execute", return_value={"repo": {"name": "test"}}) as mock_exec:
            connector.call(
                "POST", "",
                data={
                    "query": "query($owner: String!) { repository(owner: $owner) { name } }",
                    "variables": {"owner": "testorg"},
                },
            )
            _, kwargs = mock_exec.call_args
            assert kwargs["variable_values"] == {"owner": "testorg"}

    def test_health_check_disconnected(self, config: ConnectorConfig) -> None:
        """health_check reports unhealthy when disconnected."""
        connector = GraphQLConnector(config)
        health = connector.health_check()
        assert health.healthy is False

    def test_health_check_connected(self, config: ConnectorConfig) -> None:
        """health_check reports healthy when connected."""
        connector = GraphQLConnector(config)
        connector.connect()
        health = connector.health_check()
        assert health.healthy is True

    def test_to_connector_model(self, config: ConnectorConfig) -> None:
        """to_connector() returns a Connector model."""
        connector = GraphQLConnector(config)
        model = connector.to_connector()
        assert model.config.id == "gh-graphql"
        assert model.status == ConnectorStatus.DISCONNECTED

    def test_error_counting(self, config: ConnectorConfig) -> None:
        """Errors increment the error counter."""
        connector = GraphQLConnector(config)
        connector.connect()

        with patch.object(connector._client, "execute", side_effect=Exception("timeout")):
            result = connector.call("POST", "", data={"query": "{ bad }"})

        assert result.success is False
        assert connector._error_count == 1
