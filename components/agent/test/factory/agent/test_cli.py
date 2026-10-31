"""Tests for CLI commands."""

import pytest
from pathlib import Path
import tempfile
from click.testing import CliRunner

from factory.agent.cli import cli


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestCLI:
    """Tests for CLI commands."""

    def test_version(self, runner):
        """Test --version flag."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self, runner):
        """Test --help flag."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Super Agent CLI" in result.output
        assert "init" in result.output
        assert "run" in result.output
        assert "check" in result.output


class TestInitCommand:
    """Tests for 'init' command."""

    def test_init_creates_structure(self, runner, temp_dir):
        """Test init creates correct directory structure."""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            result = runner.invoke(cli, ["init", "my-project"])

            assert result.exit_code == 0
            assert "Created my-project/" in result.output

            # Check directories created
            project = Path("my-project")
            assert project.exists()
            assert (project / "config").exists()
            assert (project / "config" / "agents").exists()
            assert (project / "config" / "swarms").exists()
            assert (project / "config" / "graphs").exists()
            assert (project / "config" / "tools").exists()

    def test_init_creates_files(self, runner, temp_dir):
        """Test init creates required files."""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            result = runner.invoke(cli, ["init", "test-project"])

            assert result.exit_code == 0

            project = Path("test-project")
            assert (project / "config" / "settings.yaml").exists()
            assert (project / "config" / "tools" / "__init__.py").exists()
            assert (project / "main.py").exists()
            assert (project / "pyproject.toml").exists()

    def test_init_config_only(self, runner, temp_dir):
        """Test init with --config-only flag."""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            result = runner.invoke(cli, ["init", "config-only-project", "--config-only"])

            assert result.exit_code == 0

            project = Path("config-only-project")
            assert (project / "config").exists()
            assert not (project / "pyproject.toml").exists()

    def test_init_example_agent(self, runner, temp_dir):
        """Test init creates example agent config."""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            runner.invoke(cli, ["init", "example-project"])

            example_agent = Path("example-project/config/agents/example.yaml")
            assert example_agent.exists()

            content = example_agent.read_text()
            assert "example_agent" in content
            assert "system_prompt" in content


class TestCheckCommand:
    """Tests for 'check' command."""

    def test_check_valid_config(self, runner, temp_dir):
        """Test check with valid configuration."""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # First create a project
            runner.invoke(cli, ["init", "valid-project"])

            # Then check it
            result = runner.invoke(cli, ["check", "--config", "valid-project/config"])

            assert result.exit_code == 0
            assert "Configuration valid" in result.output

    def test_check_shows_counts(self, runner, temp_dir):
        """Test check shows agent/swarm/graph counts."""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            runner.invoke(cli, ["init", "count-project"])

            result = runner.invoke(cli, ["check", "--config", "count-project/config"])

            assert result.exit_code == 0
            assert "Agents" in result.output
            assert "Swarms" in result.output
            assert "Graphs" in result.output
