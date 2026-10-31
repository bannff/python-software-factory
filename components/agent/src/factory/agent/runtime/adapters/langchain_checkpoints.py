"""Lifecycle ownership for the official LangGraph SQLite saver."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any


class AsyncSqliteCheckpoints:
    """Own one lazy connection and official saver for an Agent runtime."""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._connection: Any | None = None
        self._saver: Any | None = None
        self._pending_deletes: set[str] = set()
        self._lock = asyncio.Lock()
        self._closed = False

    async def get(self) -> Any:
        async with self._lock:
            if self._closed:
                raise RuntimeError("checkpoint store is closed")
            if self._saver is None:
                await self._open()
            for thread_id in tuple(self._pending_deletes):
                await self._saver.adelete_thread(thread_id)
                self._pending_deletes.discard(thread_id)
            return self._saver

    async def history(self, key: str) -> tuple[Any, ...]:
        """Read messages from one exact Agent-owned checkpoint key."""
        saver = await self.get()
        item = await saver.aget_tuple({"configurable": {"thread_id": key}})
        if item is None:
            return ()
        values = item.checkpoint.get("channel_values", {})
        return tuple(values.get("messages", ()))

    async def checkpoint_before_message(self, key: str, message_id: str) -> str | None:
        """Row 16 (feature-map) — find the checkpoint id to resume from in
        order to regenerate the reply to a specific human message.

        ``channel_values.messages`` is CUMULATIVE at every checkpoint (the
        graph's ``MessagesState`` reducer appends, it never replaces —
        verified empirically against the real installed LangGraph library
        before this was written, not assumed from the LangGraph docs).
        Walking ``alist()`` newest-first and returning the FIRST checkpoint
        whose own message list already ends in ``message_id`` gives the
        exact state right after that human turn was received but BEFORE
        its reply was produced — the correct resume point for a
        regenerate. Returns ``None`` if the id never appears (unknown
        message, or it belongs to a different branch than the one this
        walk is anchored on).
        """
        saver = await self.get()
        async for item in saver.alist({"configurable": {"thread_id": key}}):
            messages = item.checkpoint.get("channel_values", {}).get("messages", ())
            if messages and str(getattr(messages[-1], "id", "")) == message_id:
                return item.checkpoint["id"]
        return None

    async def copy_thread(self, source_key: str, target_key: str) -> bool:
        """Row 14 (feature-map) — fork a session's transcript.

        ``AsyncSqliteSaver.acopy_thread``/``copy_thread`` are BOTH real,
        documented entries on ``BaseCheckpointSaver`` -- but confirmed by
        direct inspection (not assumed) to be unimplemented stubs on this
        concrete saver (``NotImplementedError``, inherited from the base,
        never overridden). Implemented here at the SQL layer instead,
        following the exact same contract the docstring describes: copy
        every row of BOTH ``checkpoints`` and ``writes`` for the source
        thread -- the complete parent chain, not just the head -- so a
        ``DeltaChannel``-backed key can still reconstruct its state on the
        target thread. ``parent_checkpoint_id`` values are NOT
        thread-qualified in this schema (confirmed via ``PRAGMA
        table_info``), so no chain remapping is needed; only ``thread_id``
        changes per row. Returns False (no-op) when the source thread has
        no checkpoint yet -- a session with zero turns forks into an
        equally empty one, which is correct, not an error.
        """
        saver = await self.get()
        connection = self._connection
        if connection is None:
            raise RuntimeError("checkpoint store is closed")
        cursor = await connection.execute(
            "SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, "
            "type, checkpoint, metadata FROM checkpoints WHERE thread_id = ?",
            (source_key,),
        )
        checkpoint_rows = await cursor.fetchall()
        if not checkpoint_rows:
            return False
        cursor = await connection.execute(
            "SELECT thread_id, checkpoint_ns, checkpoint_id, task_id, idx, "
            "channel, type, value FROM writes WHERE thread_id = ?",
            (source_key,),
        )
        write_rows = await cursor.fetchall()
        await connection.executemany(
            "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, "
            "parent_checkpoint_id, type, checkpoint, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(target_key, *row[1:]) for row in checkpoint_rows],
        )
        if write_rows:
            await connection.executemany(
                "INSERT INTO writes (thread_id, checkpoint_ns, checkpoint_id, "
                "task_id, idx, channel, type, value) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(target_key, *row[1:]) for row in write_rows],
            )
        await connection.commit()
        del saver  # only used to ensure setup() has run before touching tables
        return True

    def queue_delete(self, thread_ids: set[str]) -> None:
        if self._closed:
            raise RuntimeError("checkpoint store is closed")
        self._pending_deletes.update(thread_ids)

    async def close(self) -> None:
        if self._pending_deletes:
            await self.get()
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._connection is not None:
                await self._connection.close()
            self._connection = None
            self._saver = None

    async def _open(self) -> None:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        connection = await aiosqlite.connect(self._path)
        try:
            await connection.execute("PRAGMA journal_mode=WAL")
            await connection.commit()
            saver = AsyncSqliteSaver(connection)
            await saver.setup()
        except Exception:
            await connection.close()
            raise
        self._connection = connection
        self._saver = saver


__all__ = ["AsyncSqliteCheckpoints"]
