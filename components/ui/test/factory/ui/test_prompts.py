"""Tests for MCP prompts."""

from factory.ui import prompts as prm


class TestPrompts:
    """Tests for MCP prompts."""

    def test_list_prompts(self):
        """Should list all available prompts."""
        prompts = prm.list_prompts()

        assert len(prompts) > 0
        names = [p["name"] for p in prompts]
        assert "create_dashboard" in names
        assert "add_visualization" in names
        assert "design_form" in names

    def test_get_prompt_create_dashboard(self):
        """Should return create_dashboard prompt with arguments."""
        result = prm.get_prompt(
            "create_dashboard",
            {
                "name": "Sales Dashboard",
                "purpose": "Track sales metrics",
                "metrics": "Revenue, Orders, Customers",
                "data": "Monthly sales data",
            },
        )

        assert result["name"] == "create_dashboard"
        assert "messages" in result
        content = result["messages"][0]["content"]["text"]
        assert "Sales Dashboard" in content
        assert "Track sales metrics" in content

    def test_get_prompt_add_visualization(self):
        """Should return add_visualization prompt."""
        result = prm.get_prompt(
            "add_visualization",
            {
                "view_id": "dashboard-1",
                "data": '[{"month": "Jan", "value": 100}]',
                "title": "Monthly Trend",
            },
        )

        content = result["messages"][0]["content"]["text"]
        assert "dashboard-1" in content
        assert "Monthly Trend" in content

    def test_get_prompt_design_form(self):
        """Should return design_form prompt."""
        result = prm.get_prompt(
            "design_form",
            {
                "purpose": "Contact form",
                "fields": "Name, Email, Message",
            },
        )

        content = result["messages"][0]["content"]["text"]
        assert "Contact form" in content
        assert "Name, Email, Message" in content

    def test_get_prompt_unknown(self):
        """Should handle unknown prompt."""
        result = prm.get_prompt("unknown_prompt")

        assert "error" in result

    def test_prompt_has_arguments(self):
        """Should include argument definitions."""
        prompts = prm.list_prompts()
        dashboard_prompt = next(p for p in prompts if p["name"] == "create_dashboard")

        assert "arguments" in dashboard_prompt
        arg_names = [a["name"] for a in dashboard_prompt["arguments"]]
        assert "name" in arg_names
        assert "purpose" in arg_names
