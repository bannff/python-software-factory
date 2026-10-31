import os
import shutil
import tempfile

import pytest

from factory.kb import server as kb_server


@pytest.fixture
def temp_config_dir():
    temp_dir = tempfile.mkdtemp()
    os.environ["KB_CONFIG_DIR"] = temp_dir
    os.environ["KB_CHROMA_DIR"] = os.path.join(temp_dir, "chroma")
    yield temp_dir
    shutil.rmtree(temp_dir)

    kb_server._runtime = None
    kb_server._authoring = None

    os.environ.pop("KB_CONFIG_DIR", None)
    os.environ.pop("KB_CHROMA_DIR", None)
    os.environ.pop("KB_ENABLE_AUTHORING_TOOLS", None)
