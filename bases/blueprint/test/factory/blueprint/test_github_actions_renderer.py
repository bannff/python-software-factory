"""Tests for GitHub Actions pipeline renderer."""

from __future__ import annotations

import pytest

from factory.blueprint.runtime.renderers.github_actions import (
    GitHubActionsRenderer,
    _DEFAULT_STAGES,
)


@pytest.fixture
def renderer():
    return GitHubActionsRenderer()


# ── Basic Rendering ────────────────────────────────────────────────

class TestRendererType:
    def test_type_is_github_actions(self, renderer):
        assert renderer.renderer_type == "github_actions"


class TestDefaultStages:
    def test_default_stages_present(self, renderer):
        out = renderer.render("myproj")
        assert out.metadata["stages"] == _DEFAULT_STAGES

    def test_generates_workflow_file(self, renderer):
        out = renderer.render("myproj")
        assert ".github/workflows/deploy-infra.yml" in out.files

    def test_entry_point(self, renderer):
        out = renderer.render("myproj")
        assert out.entry_point == ".github/workflows/deploy-infra.yml"

    def test_workflow_name_contains_project(self, renderer):
        out = renderer.render("myproj")
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "myproj" in content

    def test_has_test_job(self, renderer):
        out = renderer.render("proj")
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "test:" in content
        assert "pytest" in content

    def test_has_synth_job(self, renderer):
        out = renderer.render("proj")
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "synth:" in content
        assert "cdk synth" in content

    def test_has_deploy_staging(self, renderer):
        out = renderer.render("proj")
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "deploy-staging:" in content

    def test_has_deploy_prod(self, renderer):
        out = renderer.render("proj")
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "deploy-prod:" in content


# ── OIDC Authentication ───────────────────────────────────────────

class TestOidc:
    def test_oidc_permissions(self, renderer):
        out = renderer.render("proj")
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "id-token: write" in content

    def test_oidc_step_in_synth(self, renderer):
        out = renderer.render("proj")
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "configure-aws-credentials@v4" in content

    def test_no_hardcoded_secrets(self, renderer):
        out = renderer.render("proj")
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "AWS_ACCESS_KEY" not in content
        assert "AWS_SECRET" not in content

    def test_auth_metadata(self, renderer):
        out = renderer.render("proj")
        assert out.metadata["auth"] == "oidc"


# ── Custom Stages ──────────────────────────────────────────────────

class TestCustomStages:
    def test_custom_stages_used(self, renderer):
        stages = ["test", "deploy-dev"]
        out = renderer.render("proj", stages=stages)
        assert out.metadata["stages"] == stages

    def test_only_test_stage(self, renderer):
        out = renderer.render("proj", stages=["test"])
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "test:" in content
        assert "synth:" not in content

    def test_deploy_without_synth(self, renderer):
        """Deploy stage falls back to needs: test when synth absent."""
        out = renderer.render("proj", stages=["test", "deploy-qa"])
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "deploy-qa:" in content
        assert "needs: test" in content

    def test_deploy_with_synth(self, renderer):
        out = renderer.render("proj", stages=["test", "synth", "deploy-qa"])
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "needs: synth" in content

    def test_empty_stages_uses_default(self, renderer):
        """None stages falls back to defaults."""
        out = renderer.render("proj", stages=None)
        assert out.metadata["stages"] == _DEFAULT_STAGES


# ── Workflow Structure ─────────────────────────────────────────────

class TestWorkflowStructure:
    def test_trigger_on_push(self, renderer):
        out = renderer.render("proj")
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "push:" in content
        assert "branches: [main]" in content

    def test_trigger_on_dispatch(self, renderer):
        out = renderer.render("proj")
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "workflow_dispatch:" in content

    def test_path_filter(self, renderer):
        out = renderer.render("proj")
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert 'cdk/**' in content

    def test_python_version(self, renderer):
        out = renderer.render("proj")
        content = out.files[".github/workflows/deploy-infra.yml"]
        assert "3.13" in content
