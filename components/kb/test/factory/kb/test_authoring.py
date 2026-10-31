"""Tests for authoring security."""

import os

from factory.kb.authoring import KBAuthoring


class TestAuthoringDisabledByDefault:
    """Tests that authoring is disabled by default."""

    def test_authoring_disabled_by_default(self, tmp_path):
        """Test authoring is disabled when env var not set."""
        os.environ.pop("KB_ENABLE_AUTHORING_TOOLS", None)
        
        authoring = KBAuthoring(tmp_path)
        assert authoring.is_enabled() is False

    def test_authoring_enabled_with_env_var(self, tmp_path):
        """Test authoring is enabled with env var."""
        os.environ["KB_ENABLE_AUTHORING_TOOLS"] = "1"
        try:
            authoring = KBAuthoring(tmp_path)
            assert authoring.is_enabled() is True
        finally:
            os.environ.pop("KB_ENABLE_AUTHORING_TOOLS", None)


class TestAuthoringPathScoping:
    """Tests for path scoping security."""

    def test_rejects_path_traversal(self, tmp_path):
        """Test that path traversal is rejected."""
        os.environ["KB_ENABLE_AUTHORING_TOOLS"] = "1"
        try:
            authoring = KBAuthoring(tmp_path)
            result = authoring.upsert_collection_config(
                "../../../etc/passwd",
                {"id": "test", "name": "Test"},
            )
            assert result["ok"] is False
            assert "traversal" in result["error"].lower() or "invalid" in result["error"].lower()
        finally:
            os.environ.pop("KB_ENABLE_AUTHORING_TOOLS", None)

    def test_rejects_absolute_path(self, tmp_path):
        """Test that absolute paths are rejected."""
        os.environ["KB_ENABLE_AUTHORING_TOOLS"] = "1"
        try:
            authoring = KBAuthoring(tmp_path)
            result = authoring.upsert_collection_config(
                "/etc/passwd",
                {"id": "test", "name": "Test"},
            )
            assert result["ok"] is False
        finally:
            os.environ.pop("KB_ENABLE_AUTHORING_TOOLS", None)


class TestAuthoringOperations:
    """Tests for authoring operations when enabled."""

    def test_upsert_collection_config(self, tmp_path):
        """Test upserting a collection config."""
        os.environ["KB_ENABLE_AUTHORING_TOOLS"] = "1"
        try:
            authoring = KBAuthoring(tmp_path)
            result = authoring.upsert_collection_config(
                "test-collection",
                {
                    "id": "test-collection",
                    "name": "Test Collection",
                },
            )
            assert result["ok"] is True
        finally:
            os.environ.pop("KB_ENABLE_AUTHORING_TOOLS", None)

    def test_delete_collection_config(self, tmp_path):
        """Test deleting a collection config."""
        os.environ["KB_ENABLE_AUTHORING_TOOLS"] = "1"
        try:
            authoring = KBAuthoring(tmp_path)
            # First create
            authoring.upsert_collection_config(
                "test-collection",
                {"id": "test-collection", "name": "Test"},
            )
            # Then delete
            result = authoring.delete_collection_config("test-collection")
            assert result["ok"] is True
        finally:
            os.environ.pop("KB_ENABLE_AUTHORING_TOOLS", None)
