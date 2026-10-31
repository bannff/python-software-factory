"""Tests for S3 blob storage adapter.

Tests are skipped if boto3 is not installed or AWS credentials are not available.
For local testing, use MinIO with endpoint_url override.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

# Check if boto3 is available
try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from factory.storage.runtime.adapters.blob_s3 import S3BlobStore, BOTO3_AVAILABLE as MODULE_BOTO3


@pytest.mark.skipif(not BOTO3_AVAILABLE, reason="boto3 not installed")
class TestS3BlobStoreMocked:
    """Tests for S3BlobStore with mocked boto3 client."""

    @pytest.fixture
    def mock_client(self):
        """Create a mocked S3 client."""
        return MagicMock()

    @pytest.fixture
    def store(self, mock_client):
        """Create S3BlobStore with mocked client."""
        with patch("boto3.client", return_value=mock_client):
            store = S3BlobStore(bucket="test-bucket", region="us-east-1")
            store._client = mock_client
            return store

    def test_put_blob(self, store, mock_client) -> None:
        """Test storing a blob to S3."""
        data = b"hello world"
        meta = store.put("test.txt", data, "text/plain")

        mock_client.put_object.assert_called_once()
        call_args = mock_client.put_object.call_args
        assert call_args.kwargs["Bucket"] == "test-bucket"
        assert call_args.kwargs["Key"] == "test.txt"
        assert call_args.kwargs["Body"] == data
        assert meta.key == "test.txt"
        assert meta.size == len(data)

    def test_get_blob(self, store, mock_client) -> None:
        """Test retrieving a blob from S3."""
        mock_body = MagicMock()
        mock_body.read.return_value = b"content"
        mock_client.get_object.return_value = {
            "Body": mock_body,
            "ContentType": "text/plain",
            "ETag": '"abc123"',
            "Metadata": {"key": "value"},
        }

        content, meta = store.get("test.txt")

        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="test.txt"
        )
        assert content == b"content"
        assert meta.key == "test.txt"
        assert meta.content_type == "text/plain"

    def test_delete_blob(self, store, mock_client) -> None:
        """Test deleting a blob from S3."""
        result = store.delete("test.txt")

        mock_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="test.txt"
        )
        assert result is True

    def test_delete_blob_error(self, store, mock_client) -> None:
        """Test delete returns False on error."""
        mock_client.delete_object.side_effect = Exception("Access denied")
        result = store.delete("test.txt")
        assert result is False

    def test_exists_true(self, store, mock_client) -> None:
        """Test exists returns True when object exists."""
        mock_client.head_object.return_value = {}
        assert store.exists("test.txt") is True

    def test_exists_false(self, store, mock_client) -> None:
        """Test exists returns False when object doesn't exist."""
        mock_client.head_object.side_effect = Exception("Not found")
        assert store.exists("test.txt") is False

    def test_list_keys(self, store, mock_client) -> None:
        """Test listing keys with prefix."""
        mock_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "a/file1.txt", "Size": 10, "ETag": '"abc"'},
                {"Key": "a/file2.txt", "Size": 20, "ETag": '"def"'},
            ]
        }

        results = store.list_keys(prefix="a/", limit=100)

        mock_client.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket", Prefix="a/", MaxKeys=100
        )
        assert len(results) == 2
        assert results[0].key == "a/file1.txt"

    def test_health_check_healthy(self, store, mock_client) -> None:
        """Test health check when bucket is accessible."""
        mock_client.head_bucket.return_value = {}
        health = store.health_check()

        assert health.healthy is True
        assert health.backend == "s3"
        assert health.details["bucket"] == "test-bucket"

    def test_health_check_unhealthy(self, store, mock_client) -> None:
        """Test health check when bucket is not accessible."""
        mock_client.head_bucket.side_effect = Exception("Access denied")
        health = store.health_check()

        assert health.healthy is False
        assert health.backend == "s3"
        assert "Access denied" in health.message


class TestS3BlobStoreImport:
    """Tests for S3BlobStore import behavior."""

    def test_boto3_availability_flag(self) -> None:
        """Test that BOTO3_AVAILABLE flag is set correctly."""
        assert MODULE_BOTO3 == BOTO3_AVAILABLE

    @pytest.mark.skipif(BOTO3_AVAILABLE, reason="Test requires boto3 to be missing")
    def test_require_boto3_raises(self) -> None:
        """Test that _require_boto3 raises when boto3 is missing."""
        from factory.storage.runtime.adapters.blob_s3 import _require_boto3
        with pytest.raises(ImportError, match="boto3 required"):
            _require_boto3()
