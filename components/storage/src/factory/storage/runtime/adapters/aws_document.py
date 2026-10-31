"""AWS DynamoDB document storage adapter.

Implements DocumentStore protocol using a single DynamoDB table
with collection mapped to a sort key prefix.
"""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from factory.storage.runtime.ports import Document, StorageHealth

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-]{1,255}$")


def _require_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError:
        msg = "pip install boto3 — required for DynamoDB document adapter"
        raise ImportError(msg)


def _validate_name(value: str, label: str = "identifier") -> str:
    if not _SAFE_NAME.match(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


class DynamoDBDocumentStore:
    """DynamoDB implementation of DocumentStore port.

    Uses a single table with pk=collection, sk=doc_id layout.
    """

    def __init__(self, table_name: str = "factory-documents", region: str = "us-east-1") -> None:
        _require_boto3()
        import boto3

        _validate_name(table_name, "table_name")
        self._table_name = table_name
        self._region = region
        self._table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    def insert(
        self, collection: str, data: dict[str, Any], doc_id: str | None = None,
    ) -> Document:
        _validate_name(collection, "collection")
        doc_id = doc_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        item = {
            "pk": collection,
            "sk": doc_id,
            "data": data,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        self._table.put_item(Item=item)
        return Document(id=doc_id, collection=collection, data=data,
                        created_at=now, updated_at=now)

    def get(self, collection: str, doc_id: str) -> Document | None:
        _validate_name(collection, "collection")
        resp = self._table.get_item(Key={"pk": collection, "sk": doc_id})
        item = resp.get("Item")
        return self._item_to_doc(item) if item else None

    def update(
        self, collection: str, doc_id: str, data: dict[str, Any],
    ) -> Document | None:
        _validate_name(collection, "collection")
        existing = self.get(collection, doc_id)
        if not existing:
            return None
        now = datetime.now(timezone.utc)
        merged = {**existing.data, **data}
        self._table.update_item(
            Key={"pk": collection, "sk": doc_id},
            UpdateExpression="SET #d = :d, updated_at = :u",
            ExpressionAttributeNames={"#d": "data"},
            ExpressionAttributeValues={":d": merged, ":u": now.isoformat()},
        )
        return Document(id=doc_id, collection=collection, data=merged,
                        created_at=existing.created_at, updated_at=now)

    def delete(self, collection: str, doc_id: str) -> bool:
        _validate_name(collection, "collection")
        self._table.delete_item(Key={"pk": collection, "sk": doc_id})
        return True

    def find(
        self, collection: str, query: dict[str, Any],
        limit: int = 100, skip: int = 0,
    ) -> list[Document]:
        _validate_name(collection, "collection")
        from boto3.dynamodb.conditions import Key

        resp = self._table.query(
            KeyConditionExpression=Key("pk").eq(collection),
            Limit=limit + skip,
        )
        items = resp.get("Items", [])[skip:skip + limit]
        if query:
            items = [i for i in items if self._matches(i.get("data", {}), query)]
        return [self._item_to_doc(i) for i in items]

    def count(self, collection: str, query: dict[str, Any] | None = None) -> int:
        return len(self.find(collection, query or {}, limit=100000))

    def list_collections(self) -> list[str]:
        resp = self._table.scan(ProjectionExpression="pk")
        return list({item["pk"] for item in resp.get("Items", [])})

    def health_check(self) -> StorageHealth:
        start = time.time()
        try:
            self._table.table_status  # noqa: B018
            latency = (time.time() - start) * 1000
            return StorageHealth(healthy=True, backend="dynamodb", latency_ms=latency,
                                 details={"table": self._table_name, "region": self._region})
        except Exception as e:
            return StorageHealth(healthy=False, backend="dynamodb", message=str(e))

    def infrastructure_spec(self) -> dict[str, Any]:
        return {
            "service": "dynamodb",
            "construct": "Table",
            "props": {
                "table_name": self._table_name,
                "partition_key": {"name": "pk", "type": "S"},
                "sort_key": {"name": "sk", "type": "S"},
                "billing_mode": "PAY_PER_REQUEST",
            },
        }

    @staticmethod
    def _matches(data: dict[str, Any], query: dict[str, Any]) -> bool:
        return all(data.get(k) == v for k, v in query.items())

    @staticmethod
    def _item_to_doc(item: dict[str, Any]) -> Document:
        return Document(
            id=item["sk"],
            collection=item["pk"],
            data=item.get("data", {}),
            created_at=datetime.fromisoformat(item["created_at"]) if "created_at" in item else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(item["updated_at"]) if "updated_at" in item else datetime.now(timezone.utc),
        )
