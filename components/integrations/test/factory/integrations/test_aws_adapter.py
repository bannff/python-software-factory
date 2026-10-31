"""Tests for AWS connector adapter."""

import pytest
from unittest.mock import MagicMock, patch

from factory.integrations.core import ConnectorStatus
from factory.integrations.runtime.adapters.aws import AWSConnector
from factory.integrations.runtime.models import ConnectorConfig


class TestAWSConnector:
    """Test AWS connector adapter."""

    @pytest.fixture
    def config(self) -> ConnectorConfig:
        """Create test connector config."""
        return ConnectorConfig(
            id="test-aws",
            name="Test AWS Connector",
            connector_type="aws",
            base_url="aws://ec2",
            metadata={"region": "us-east-1"},
        )

    @pytest.fixture
    def connector(self, config: ConnectorConfig) -> AWSConnector:
        """Create AWS connector."""
        return AWSConnector(config)

    def test_init(self, connector: AWSConnector) -> None:
        """Test connector initialization."""
        assert connector.status == ConnectorStatus.DISCONNECTED
        assert connector._service_name == "ec2"

    def test_extract_service_name_from_url(self) -> None:
        """Test service name extraction from aws:// URL."""
        config = ConnectorConfig(
            id="test",
            name="Test",
            connector_type="aws",
            base_url="aws://ssm",
        )
        connector = AWSConnector(config)
        assert connector._service_name == "ssm"

    def test_extract_service_name_from_metadata(self) -> None:
        """Test service name extraction from metadata."""
        config = ConnectorConfig(
            id="test",
            name="Test",
            connector_type="aws",
            base_url="https://example.com",
            metadata={"service": "s3"},
        )
        connector = AWSConnector(config)
        assert connector._service_name == "s3"

    def test_is_connected_when_disconnected(self, connector: AWSConnector) -> None:
        """Test is_connected returns False when disconnected."""
        assert connector.is_connected() is False

    @patch("boto3.Session")
    def test_connect_success(self, mock_session: MagicMock, connector: AWSConnector) -> None:
        """Test successful connection."""
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        result = connector.connect()

        assert result is True
        assert connector.status == ConnectorStatus.CONNECTED
        assert connector.is_connected() is True
        mock_session.assert_called_once_with(region_name="us-east-1")

    @patch("boto3.Session")
    def test_connect_with_profile(self, mock_session: MagicMock) -> None:
        """Test connection with AWS profile."""
        config = ConnectorConfig(
            id="test",
            name="Test",
            connector_type="aws",
            base_url="aws://ec2",
            metadata={"region": "us-west-2", "profile": "dev"},
        )
        connector = AWSConnector(config)
        mock_session.return_value.client.return_value = MagicMock()

        connector.connect()

        mock_session.assert_called_once_with(region_name="us-west-2", profile_name="dev")

    @patch("boto3.Session")
    def test_connect_failure(self, mock_session: MagicMock, connector: AWSConnector) -> None:
        """Test connection failure."""
        mock_session.side_effect = Exception("AWS error")

        result = connector.connect()

        assert result is False
        assert connector.status == ConnectorStatus.ERROR
        assert "AWS error" in connector._last_error

    @patch("boto3.Session")
    def test_disconnect(self, mock_session: MagicMock, connector: AWSConnector) -> None:
        """Test disconnection."""
        mock_session.return_value.client.return_value = MagicMock()
        connector.connect()

        connector.disconnect()

        assert connector.status == ConnectorStatus.DISCONNECTED
        assert connector._client is None

    @patch("boto3.Session")
    def test_call_success(self, mock_session: MagicMock, connector: AWSConnector) -> None:
        """Test successful API call."""
        mock_client = MagicMock()
        mock_client.describe_instances.return_value = {
            "Reservations": [],
            "ResponseMetadata": {"RequestId": "123"},
        }
        mock_session.return_value.client.return_value = mock_client
        connector.connect()

        result = connector.call("describe_instances", params={"MaxResults": 10})

        assert result.success is True
        assert result.data == {"Reservations": []}  # ResponseMetadata removed
        assert result.latency_ms > 0
        mock_client.describe_instances.assert_called_once_with(MaxResults=10)

    @patch("boto3.Session")
    def test_call_not_connected(self, mock_session: MagicMock, connector: AWSConnector) -> None:
        """Test call when not connected."""
        result = connector.call("describe_instances")

        assert result.success is False
        assert "Not connected" in result.error

    @patch("boto3.Session")
    def test_call_unknown_operation(self, mock_session: MagicMock, connector: AWSConnector) -> None:
        """Test call with unknown operation."""
        mock_client = MagicMock(spec=[])  # No methods
        mock_session.return_value.client.return_value = mock_client
        connector.connect()

        result = connector.call("unknown_operation")

        assert result.success is False
        assert "Unknown operation" in result.error

    @patch("boto3.Session")
    def test_call_failure(self, mock_session: MagicMock, connector: AWSConnector) -> None:
        """Test API call failure."""
        mock_client = MagicMock()
        mock_client.describe_instances.side_effect = Exception("API error")
        mock_session.return_value.client.return_value = mock_client
        connector.connect()

        result = connector.call("describe_instances")

        assert result.success is False
        assert "API error" in result.error
        assert connector._error_count == 1

    @patch("boto3.Session")
    def test_to_connector(self, mock_session: MagicMock, connector: AWSConnector) -> None:
        """Test conversion to Connector model."""
        mock_session.return_value.client.return_value = MagicMock()
        connector.connect()

        model = connector.to_connector()

        assert model.config.id == "test-aws"
        assert model.status == ConnectorStatus.CONNECTED
        assert model.request_count == 0

    @patch("boto3.Session")
    def test_health_check_connected(self, mock_session: MagicMock, connector: AWSConnector) -> None:
        """Test health check when connected."""
        mock_session.return_value.client.return_value = MagicMock()
        connector.connect()

        with patch("boto3.client") as mock_sts:
            mock_sts.return_value.get_caller_identity.return_value = {}
            health = connector.health_check()

        assert health.healthy is True
        assert health.connected_count == 1

    def test_health_check_disconnected(self, connector: AWSConnector) -> None:
        """Test health check when disconnected."""
        health = connector.health_check()

        assert health.healthy is False
        assert health.connected_count == 0
        assert "Not connected" in health.message
