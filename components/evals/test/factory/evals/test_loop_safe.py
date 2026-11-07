"""Sync SDK calls must work from inside a running event loop (issue #307)."""
import asyncio

from factory.evals.runtime.adapters.loop_safe import call_off_loop


def _nested_asyncio_run() -> str:
    async def inner() -> str:
        return "ok"
    return asyncio.run(inner())


def test_plain_call_without_loop():
    assert call_off_loop(_nested_asyncio_run) == "ok"


def test_call_inside_running_loop_does_not_nest():
    async def outer() -> str:
        return call_off_loop(_nested_asyncio_run)
    assert asyncio.run(outer()) == "ok"


def test_exceptions_propagate_from_worker_thread():
    def boom() -> None:
        raise ValueError("x")

    async def outer() -> None:
        call_off_loop(boom)
    try:
        asyncio.run(outer())
    except ValueError as exc:
        assert str(exc) == "x"
    else:
        raise AssertionError("expected ValueError")
