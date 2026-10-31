"""Tests for UI actions."""

import pytest

from factory.evals.runtime.ui import (
    Click,
    Fill,
    Hover,
    WaitFor,
    Navigate,
    PressKey,
)


class TestUIActions:
    """Tests for UI actions."""

    def test_click_action(self):
        """Click action serializes correctly."""
        action = Click(target="btn-submit", double_click=True)
        data = action.to_dict()
        
        assert data["type"] == "click"
        assert data["target"] == "btn-submit"
        assert data["doubleClick"] is True

    def test_fill_action(self):
        """Fill action serializes correctly."""
        action = Fill(target="email", value="test@example.com")
        data = action.to_dict()
        
        assert data["type"] == "fill"
        assert data["target"] == "email"
        assert data["value"] == "test@example.com"

    def test_hover_action(self):
        """Hover action serializes correctly."""
        action = Hover(target="menu-item")
        assert action.action_type == "hover"

    def test_wait_action(self):
        """Wait action serializes correctly."""
        action = WaitFor(text="Dashboard")
        data = action.to_dict()
        
        assert data["type"] == "wait"
        assert data["text"] == "Dashboard"

    def test_navigate_action(self):
        """Navigate action serializes correctly."""
        action = Navigate(url="/dashboard")
        data = action.to_dict()
        
        assert data["type"] == "navigate"
        assert data["url"] == "/dashboard"

    def test_press_key_action(self):
        """Press key action serializes correctly."""
        action = PressKey(key="Enter")
        data = action.to_dict()
        
        assert data["type"] == "press_key"
        assert data["key"] == "Enter"
