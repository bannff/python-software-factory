"""S3 blob storage adapter."""

from __future__ import annotations

import hashlib
import importlib.util
import time
from datetime import datetime, timezone
from typing import Any, BinaryIO

from factory.storage.runtime.ports import BlobMetadata, StorageHealth

BOTO3_AVAILABLE = importlib.util.find_spec("boto3") is not None


def _require_boto3() -> None:
    if not BOTO3_AVAILABLE:
        raise ImportError("boto3 required. Install with: pip install boto3")


class S3BlobStore:
    """S3 implementation of BlobStore port."""

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        _require_boto3()
        import boto3
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            **kwargs,
        )

    def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> BlobMetadata:
        """Store a blob to S3."""
        if isinstance(data, bytes):
            content = data
        else:
            content = data.read()

        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            Metadata=metadata or {},
        )

        return BlobMetadata(
            key=key,
            size=len(content),
            content_type=content_type,
            etag=hashlib.md5(content).hexdigest(),
            last_modified=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

    def get(self, key: str) -> tuple[bytes, BlobMetadata]:
        """Retrieve a blob from S3."""
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        content = response["Body"].read()

        return content, BlobMetadata(
            key=key,
            size=len(content),
            content_type=response.get("ContentType", "application/octet-stream"),
            etag=response.get("ETag", "").strip('"'),
            last_modified=response.get("LastModified", datetime.now(timezone.utc)),
            metadata=response.get("Metadata", {}),
        )

    def delete(self, key: str) -> bool:
        """Delete a blob from S3."""
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        """Check if a blob exists in S3."""
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def list_keys(self, prefix: str = "", limit: int = 1000) -> list[BlobMetadata]:
        """List blobs with optional prefix filter."""
        response = self._client.list_objects_v2(
            Bucket=self._bucket,
            Prefix=prefix,
            MaxKeys=limit,
        )
        results = []
        for obj in response.get("Contents", []):
            results.append(BlobMetadata(
                key=obj["Key"],
                size=obj["Size"],
                etag=obj.get("ETag", "").strip('"'),
                last_modified=obj.get("LastModified", datetime.now(timezone.utc)),
            ))
        return results

    def health_check(self) -> StorageHealth:
        """Check S3 health."""
        start = time.time()
        try:
            self._client.head_bucket(Bucket=self._bucket)
            latency = (time.time() - start) * 1000
            return StorageHealth(
                healthy=True, backend="s3", latency_ms=latency,
                details={"bucket": self._bucket},
            )
        except Exception as e:
            return StorageHealth(healthy=False, backend="s3", message=str(e))
