import os
import shutil
import tempfile

import pytest
import pytest_asyncio

from factory.events.runtime.runtime import EventsRuntime


@pytest.fixture
def temp_config_dir():
    temp_dir = tempfile.mkdtemp()
    os.environ["EVENTS_CONFIG_DIR"] = temp_dir
    os.environ["EVENTS_DB_PATH"] = os.path.join(temp_dir, "test_events.db")
    yield temp_dir
    shutil.rmtree(temp_dir)
    EventsRuntime.reset()
    del os.environ["EVENTS_CONFIG_DIR"]
    del os.environ["EVENTS_DB_PATH"]


@pytest_asyncio.fixture
async def runtime(temp_config_dir):
    EventsRuntime.reset()
    return await EventsRuntime.get_store()
