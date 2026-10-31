from factory.artifacts import core
from factory.artifacts.runtime.runtime import ArtifactsRuntime


def test_sample():
    assert core is not None


def test_capability_labels_match_brick_contract() -> None:
    assert ArtifactsRuntime.get_capabilities()["features"] == [
        "stable_owner_scoped_slugs",
        "idempotent_save",
        "immutable_version_snapshots",
        "revision_fenced_lifecycle",
        "additive_version_revert",
        "opaque_tombstones",
        "content_free_lifecycle_events",
        "bounded_owner_scoped_folders",
        "one_level_comment_threads",
        "human_gated_authoring",
        "native_mcp_v2_typed_pydantic_contracts",
    ]
