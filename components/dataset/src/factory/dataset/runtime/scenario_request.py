"""Cross-check ScenarioPack request metadata before recipe execution."""
from __future__ import annotations

from .contracts import DatasetGenerationRequest, DatasetInputRef


def validate_scenario_request(
    request: DatasetGenerationRequest,
) -> DatasetInputRef | None:
    """Require one typed artifact to agree with the generation reference."""
    matches = [
        item for item in request.input_artifacts
        if item.artifact_role == "scenario_pack"
    ]
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous artifact role 'scenario_pack': {len(matches)} inputs"
        )
    generation = request.scenario_generation
    if generation is None:
        if matches:
            raise ValueError(
                "scenario_pack artifact role requires typed scenario generation input"
            )
        return None
    if not matches:
        raise ValueError("Missing required artifact role 'scenario_pack'")
    artifact = matches[0]
    ref = generation.scenario_pack
    if artifact.uri != ref.uri or artifact.digest != ref.digest:
        raise ValueError(
            "scenario_pack artifact role disagrees with typed pack reference"
        )
    return artifact
