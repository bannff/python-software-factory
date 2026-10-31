"""Tests for A2UI schema and components."""

import pytest
from factory.ui.runtime.a2ui import (
    A2UIComponent,
    A2UIPayload,
    validate_a2ui,
    get_supported_components,
    COMPONENT_CATALOG,
)


class TestA2UISchema:
    """Tests for A2UI schema validation."""

    def test_valid_payload(self):
        """Valid payload passes validation."""
        payload = {
            "components": [
                {"id": "1", "type": "Card", "props": {"title": "Test"}},
                {"id": "2", "type": "Text", "parent": "1", "props": {"content": "Hello"}},
            ]
        }
        errors = validate_a2ui(payload)
        assert len(errors) == 0

    def test_missing_components(self):
        """Missing components array fails."""
        errors = validate_a2ui({})
        assert len(errors) == 1
        assert "components" in errors[0].message.lower()

    def test_missing_id(self):
        """Component without id fails."""
        payload = {"components": [{"type": "Card"}]}
        errors = validate_a2ui(payload)
        assert any("id" in e.message.lower() for e in errors)

    def test_missing_type(self):
        """Component without type fails."""
        payload = {"components": [{"id": "1"}]}
        errors = validate_a2ui(payload)
        assert any("type" in e.message.lower() for e in errors)

    def test_duplicate_ids(self):
        """Duplicate ids fail."""
        payload = {
            "components": [
                {"id": "1", "type": "Card"},
                {"id": "1", "type": "Text"},
            ]
        }
        errors = validate_a2ui(payload)
        assert any("duplicate" in e.message.lower() for e in errors)

    def test_invalid_parent_reference(self):
        """Invalid parent reference fails."""
        payload = {
            "components": [
                {"id": "1", "type": "Card"},
                {"id": "2", "type": "Text", "parent": "nonexistent"},
            ]
        }
        errors = validate_a2ui(payload)
        assert any("not found" in e.message.lower() for e in errors)


class TestA2UIComponent:
    """Tests for A2UIComponent dataclass."""

    def test_from_dict(self):
        """Create component from dict."""
        data = {
            "id": "1",
            "type": "Card",
            "props": {"title": "Test"},
            "parent": "0",
        }
        comp = A2UIComponent.from_dict(data)
        assert comp.id == "1"
        assert comp.type == "Card"
        assert comp.props == {"title": "Test"}
        assert comp.parent == "0"

    def test_to_dict(self):
        """Convert component to dict."""
        comp = A2UIComponent(
            id="1",
            type="Button",
            props={"label": "Click"},
        )
        data = comp.to_dict()
        assert data["id"] == "1"
        assert data["type"] == "Button"
        assert data["props"] == {"label": "Click"}


class TestA2UIPayload:
    """Tests for A2UIPayload dataclass."""

    def test_from_dict(self):
        """Create payload from dict."""
        data = {
            "components": [
                {"id": "1", "type": "Card"},
            ],
            "version": "0.8",
        }
        payload = A2UIPayload.from_dict(data)
        assert len(payload.components) == 1
        assert payload.version == "0.8"

    def test_default_version(self):
        """Default version is 0.8."""
        payload = A2UIPayload.from_dict({"components": []})
        assert payload.version == "0.8"


class TestComponentCatalog:
    """Tests for component catalog."""

    def test_supported_components(self):
        """Get supported components."""
        components = get_supported_components()
        assert len(components) > 0
        
        types = [c["type"] for c in components]
        assert "Card" in types
        assert "Button" in types
        assert "Text" in types
        assert "Form" in types

    def test_catalog_has_specs(self):
        """Catalog entries have required fields."""
        for comp in get_supported_components():
            assert "type" in comp
            assert "nativeType" in comp
            assert "description" in comp
