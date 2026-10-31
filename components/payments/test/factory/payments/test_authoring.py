"""Tests for payments authoring security."""

import os
from pathlib import Path

from factory.payments.authoring import AuthoringManager


class TestAuthoringSecurity:
    """Tests for AuthoringManager security controls."""

    def setup_method(self) -> None:
        self.config_dir = Path("./payments-module/config")
        os.environ.pop("PAY_ENABLE_AUTHORING_TOOLS", None)

    def teardown_method(self) -> None:
        os.environ.pop("PAY_ENABLE_AUTHORING_TOOLS", None)

    def test_disabled_by_default(self) -> None:
        manager = AuthoringManager(self.config_dir)
        assert manager.enabled is False
        try:
            manager.validate_provider_config({})
            assert False, "Should have raised PermissionError"
        except PermissionError:
            pass

    def test_enabled_via_env(self) -> None:
        os.environ["PAY_ENABLE_AUTHORING_TOOLS"] = "1"
        manager = AuthoringManager(self.config_dir)
        assert manager.enabled is True

        valid_def = {"id": "stripe", "type": "stripe", "config": {}}
        manager.validate_provider_config(valid_def)

    def test_path_traversal_protection(self) -> None:
        os.environ["PAY_ENABLE_AUTHORING_TOOLS"] = "1"
        manager = AuthoringManager(self.config_dir)

        valid_def = {"id": "stripe", "type": "stripe", "config": {}}
        try:
            manager.upsert_provider_definition("../hack", valid_def)
            assert False, "Should have raised PermissionError"
        except PermissionError:
            pass
