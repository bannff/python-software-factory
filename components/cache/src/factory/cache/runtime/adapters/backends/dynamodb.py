"""DynamoDB backend for AWS cache adapter."""

from __future__ import annotations

import json
import time
from typing import Any

import boto3

from factory.cache.runtime.ports import CacheHealth, CacheStats


class DynamoDBBackend:
    """DynamoDB-backed cache with native TTL support."""

    def __init__(
        self,
        table_name: str = "factory-cache",
        region: str = "us-east-1",
        **kwargs: Any,
    ) -> None:
        self._table_name = table_name
        resource = boto3.resource("dynamodb", region_name=region)
        self._table = resource.Table(table_name)
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        resp = self._table.get_item(Key={"pk": key})
        item = resp.get("Item")
        if not item:
            self._misses += 1
            return None
        if item.get("ttl") and item["ttl"] < int(time.time()):
            self._misses += 1
            return None
        self._hits += 1
        return json.loads(item["value"])

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool:
        item: dict[str, Any] = {"pk": key, "value": json.dumps(value)}
        if ttl_seconds:
            item["ttl"] = int(time.time()) + ttl_seconds
        self._table.put_item(Item=item)
        return True

    def delete(self, key: str) -> bool:
        self._table.delete_item(Key={"pk": key})
        return True

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def clear(self) -> int:
        resp = self._table.scan(ProjectionExpression="pk")
        items = resp.get("Items", [])
        with self._table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"pk": item["pk"]})
        return len(items)

    def keys(self, pattern: str = "*") -> list[str]:
        resp = self._table.scan(ProjectionExpression="pk")
        all_keys = [item["pk"] for item in resp.get("Items", [])]
        if pattern == "*":
            return all_keys
        import fnmatch
        return [k for k in all_keys if fnmatch.fnmatch(k, pattern)]

    def ttl(self, key: str) -> int | None:
        resp = self._table.get_item(Key={"pk": key})
        item = resp.get("Item")
        if not item or "ttl" not in item:
            return None
        remaining = item["ttl"] - int(time.time())
        return max(0, remaining) if remaining > 0 else None

    def stats(self) -> CacheStats:
        resp = self._table.scan(Select="COUNT")
        return CacheStats(
            hits=self._hits, misses=self._misses,
            size=resp.get("Count", 0),
        )

    def health_check(self) -> CacheHealth:
        start = time.time()
        try:
            self._table.table_status  # noqa: B018
            latency = (time.time() - start) * 1000
            return CacheHealth(
                healthy=True, backend="dynamodb",
                latency_ms=latency,
                details={"table": self._table_name},
            )
        except Exception as e:
            return CacheHealth(
                healthy=False, backend="dynamodb", message=str(e),
            )

    def infrastructure_spec(self) -> dict[str, Any]:
        return {
            "service": "dynamodb",
            "construct": "Table",
            "props": {
                "table_name": self._table_name,
                "partition_key": {"name": "pk", "type": "S"},
                "billing_mode": "PAY_PER_REQUEST",
                "time_to_live_attribute": "ttl",
            },
        }
