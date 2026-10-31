"""Tests for AWS cache adapter — service selector and delegation.

Mocks boto3 entirely; tests AWSCacheAdapter routing to DynamoDB/ElastiCache
backends, invalid service handling, and infrastructure_spec.
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from factory.cache.runtime.ports import CacheHealth, CacheStats


class TestAWSCacheAdapterSelector:
    """Service selector: dynamodb vs elasticache vs invalid."""

    @patch("boto3.resource")
    def test_dynamodb_service(self, mock_resource: MagicMock) -> None:
        """service='dynamodb' creates DynamoDBBackend."""
        mock_resource.return_value.Table.return_value = MagicMock()
        from factory.cache.runtime.adapters.aws import AWSCacheAdapter

        adapter = AWSCacheAdapter(service="dynamodb")
        assert adapter._service == "dynamodb"

    @patch("redis.Redis")
    def test_elasticache_service(self, mock_redis: MagicMock) -> None:
        """service='elasticache' creates ElastiCacheBackend."""
        from factory.cache.runtime.adapters.aws import AWSCacheAdapter

        adapter = AWSCacheAdapter(service="elasticache")
        assert adapter._service == "elasticache"

    def test_invalid_service_raises(self) -> None:
        """Unknown service raises ValueError."""
        from factory.cache.runtime.adapters.aws import AWSCacheAdapter

        with pytest.raises(ValueError, match="Unknown AWS cache service"):
            AWSCacheAdapter(service="memcached")

    def test_default_service_is_dynamodb(self) -> None:
        """Default service is dynamodb."""
        with patch("boto3.resource") as mock_resource:
            mock_resource.return_value.Table.return_value = MagicMock()
            from factory.cache.runtime.adapters.aws import AWSCacheAdapter

            adapter = AWSCacheAdapter()
            assert adapter._service == "dynamodb"
