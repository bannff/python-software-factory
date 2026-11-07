"""Run blocking strands-evals calls without nesting asyncio.run in a live loop."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

T = TypeVar("T")


def call_off_loop(fn: Callable[[], T]) -> T:
    """The SDK's sync entrypoints call asyncio.run internally, which raises under
    the API's running loop; a worker thread has no loop, so it is safe there."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return fn()
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(fn).result()
