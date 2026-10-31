"""Atomic immutable writes for the Neo4j document adapter."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from factory.storage.runtime.ports import DocumentWriteResult


class Neo4jCreateOrMatchMixin:
    """Add an atomic immutable create-or-match operation to a Neo4j store."""

    def create_or_match(
        self, collection: str, doc_id: str, data: dict[str, Any], content_hash: str,
    ) -> DocumentWriteResult:
        """Atomically create data or compare the immutable stored hash."""
        if data.get("content_hash") != content_hash:
            raise ValueError("data content_hash must match content_hash")
        now = datetime.now(timezone.utc)
        props = self._flatten(data, doc_id, collection, now, now)
        query = (
            "MERGE (d:Document {id: $id}) "
            "ON CREATE SET d = $props, d._write_created = true "
            "WITH d, coalesce(d._write_created, false) AS created "
            "REMOVE d._write_created RETURN d, created"
        )
        with self._driver.session(database=self._database) as session:
            record = session.run(query, id=doc_id, props=props).single()
        document = self._node_to_doc(dict(record["d"]))
        if record["created"]:
            return DocumentWriteResult("created", document)
        existing_hash = str(document.data.get("content_hash", ""))
        status = "matched" if existing_hash and existing_hash == content_hash else "conflict"
        return DocumentWriteResult(status, document, existing_hash)
