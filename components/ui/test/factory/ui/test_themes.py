"""Tests for theme system."""

import pytest

from factory.ui.runtime.themes import (
    DaisyTheme,
    ShadcnTheme,
    DAISY_THEMES,
    SHADCN_THEMES,
    ThemeConfig,
)


class TestDaisyTheme:
    """Tests for DaisyUI theme."""

    def test_default_theme(self) -> None:
        theme = DaisyTheme()
        assert theme.name == "light"
        assert theme.variant == "light"

    def test_dark_theme(self) -> None:
        theme = DaisyTheme("dark")
        assert theme.name == "dark"
        assert theme.variant == "dark"

    def test_invalid_theme_falls_back(self) -> None:
        theme = DaisyTheme("nonexistent")
        assert theme.name == "light"

    def test_get_config(self) -> None:
        theme = DaisyTheme("cupcake")
        config = theme.get_config()
        assert isinstance(config, ThemeConfig)
        assert config.name == "cupcake"
        assert config.custom["data_theme"] == "cupcake"

    def test_get_component_classes(self) -> None:
        theme = DaisyTheme()
        classes = theme.get_component_classes("button")
        assert "base" in classes
        assert "btn" in classes["base"]
        assert "primary" in classes

    def test_semantic_colors(self) -> None:
        theme = DaisyTheme()
        config = theme.get_config()
        assert "primary" in config.colors
        assert "error" in config.colors

    def test_to_dict(self) -> None:
        theme = DaisyTheme("synthwave")
        data = theme.to_dict()
        assert data["name"] == "synthwave"
        assert data["framework"] == "daisyui"
        assert data["variant"] == "dark"

    def test_all_themes_valid(self) -> None:
        for name in DAISY_THEMES:
            theme = DaisyTheme(name)
            assert theme.name == name


class TestShadcnTheme:
    """Tests for shadcn theme."""

    def test_default_theme(self) -> None:
        theme = ShadcnTheme()
        assert theme.name == "default"
        assert theme.variant == "light"

    def test_dark_theme(self) -> None:
        theme = ShadcnTheme("dark")
        assert theme.name == "dark"
        assert theme.variant == "dark"

    def test_invalid_theme_falls_back(self) -> None:
        theme = ShadcnTheme("nonexistent")
        assert theme.name == "default"

    def test_get_config(self) -> None:
        theme = ShadcnTheme()
        config = theme.get_config()
        assert isinstance(config, ThemeConfig)
        assert "primary" in config.colors

    def test_get_css_variables(self) -> None:
        theme = ShadcnTheme()
        variables = theme.get_css_variables()
        assert "--background" in variables
        assert "--primary" in variables
        assert "--destructive" in variables

    def test_get_component_classes(self) -> None:
        theme = ShadcnTheme()
        classes = theme.get_component_classes("button")
        assert "base" in classes
        assert "default" in classes
        assert "destructive" in classes

    def test_to_dict(self) -> None:
        theme = ShadcnTheme("dark")
        data = theme.to_dict()
        assert data["name"] == "dark"
        assert data["framework"] == "shadcn"
        assert "css_variables" in data

    def test_all_themes_valid(self) -> None:
        for name in SHADCN_THEMES:
            theme = ShadcnTheme(name)
            assert theme.name == name


class TestThemeConfig:
    """Tests for ThemeConfig dataclass."""

    def test_to_dict(self) -> None:
        config = ThemeConfig(
            name="test",
            variant="light",
            colors={"primary": "#000"},
        )
        data = config.to_dict()
        assert data["name"] == "test"
        assert data["colors"]["primary"] == "#000"

    def test_defaults(self) -> None:
        config = ThemeConfig(name="minimal")
        assert config.variant == "default"
        assert config.colors == {}
        assert config.spacing == {}
