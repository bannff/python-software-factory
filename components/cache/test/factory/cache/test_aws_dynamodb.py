"""Tests for DynamoDB cache backend.

All boto3 calls are mocked — no real AWS resources needed.
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from factory.cache.runtime.ports import CacheHealth, CacheStats


@pytest.fixture
def mock_table() -> MagicMock:
    """Mock DynamoDB table resource."""
    return MagicMock()


@pytest.fixture
def backend(mock_table: MagicMock):
    """Create DynamoDBBackend with mocked boto3."""
    with patch("boto3.resource") as mock_resource:
        mock_resource.return_value.Table.return_value = mock_table
        from factory.cache.runtime.adapters.backends.dynamodb import DynamoDBBackend

        return DynamoDBBackend(table_name="test-cache", region="us-west-2")


class TestDynamoDBGet:
    """get() method tests."""

    def test_get_existing_key(self, backend, mock_table: MagicMock) -> None:
        """Returns deserialized value for existing key."""
        mock_table.get_item.return_value = {
            "Item": {"pk": "k1", "value": json.dumps({"a": 1})},
        }
        assert backend.get("k1") == {"a": 1}

    def test_get_missing_key(self, backend, mock_table: MagicMock) -> None:
        """Returns None and increments misses for missing key."""
        mock_table.get_item.return_value = {}
        assert backend.get("missing") is None

    def test_get_expired_ttl(self, backend, mock_table: MagicMock) -> None:
        """Returns None for item with expired TTL."""
        mock_table.get_item.return_value = {
            "Item": {"pk": "k", "value": '"v"', "ttl": int(time.time()) - 10},
        }
        assert backend.get("k") is None


class TestDynamoDBSet:
    """set() method tests."""

    def test_set_without_ttl(self, backend, mock_table: MagicMock) -> None:
        """Stores item without TTL attribute."""
        assert backend.set("k", "v") is True
        call_args = mock_table.put_item.call_args
        item = call_args[1]["Item"]
        assert item["pk"] == "k"
        assert json.loads(item["value"]) == "v"
        assert "ttl" not in item

    def test_set_with_ttl(self, backend, mock_table: MagicMock) -> None:
        """Stores item with TTL attribute."""
        backend.set("k", "v", ttl_seconds=60)
        item = mock_table.put_item.call_args[1]["Item"]
        assert "ttl" in item
        assert item["ttl"] > int(time.time())


class TestDynamoDBOps:
    """delete, exists, clear, keys, ttl, stats."""

    def test_delete(self, backend, mock_table: MagicMock) -> None:
        """delete() calls delete_item and returns True."""
        assert backend.delete("k") is True
        mock_table.delete_item.assert_called_once()

    def test_clear(self, backend, mock_table: MagicMock) -> None:
        """clear() scans and batch-deletes all items."""
        mock_table.scan.return_value = {
            "Items": [{"pk": "a"}, {"pk": "b"}],
        }
        batch_mock = MagicMock()
        mock_table.batch_writer.return_value.__enter__ = lambda s: batch_mock
        mock_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)
        assert backend.clear() == 2

    def test_keys_all(self, backend, mock_table: MagicMock) -> None:
        """keys('*') returns all partition keys."""
        mock_table.scan.return_value = {
            "Items": [{"pk": "x"}, {"pk": "y"}],
        }
        assert backend.keys("*") == ["x", "y"]

    def test_stats(self, backend, mock_table: MagicMock) -> None:
        """stats() returns CacheStats with scan count."""
        mock_table.scan.return_value = {"Count": 5}
        s = backend.stats()
        assert isinstance(s, CacheStats)
        assert s.size == 5


class TestDynamoDBHealth:
    """health_check() and infrastructure_spec()."""

    def test_health_check_healthy(self, backend, mock_table: MagicMock) -> None:
        """Healthy when table_status is accessible."""
        mock_table.table_status = "ACTIVE"
        h = backend.health_check()
        assert isinstance(h, CacheHealth)
        assert h.healthy is True
        assert h.backend == "dynamodb"

    def test_health_check_failure(self, backend, mock_table: MagicMock) -> None:
        """Unhealthy when table access raises."""
        type(mock_table).table_status = property(
            lambda s: (_ for _ in ()).throw(Exception("timeout")),
        )
        h = backend.health_check()
        assert h.healthy is False
        assert "timeout" in h.message

    def test_infrastructure_spec(self, backend) -> None:
        """Returns valid DynamoDB spec dict."""
        spec = backend.infrastructure_spec()
        assert spec["service"] == "dynamodb"
        assert spec["construct"] == "Table"
        assert "table_name" in spec["props"]
        assert spec["props"]["time_to_live_attribute"] == "ttl"
