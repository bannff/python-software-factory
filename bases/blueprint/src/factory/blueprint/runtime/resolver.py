"""Blueprint resolver — converts normalized resources into an InfraBlueprint.

Detects VPC requirements, generates IAM policy statements, and groups
resources by service for the renderers.
"""

from __future__ import annotations

from ..core import VPC_REQUIRED_SERVICES, SERVICE_IAM_ACTIONS
from .ports import NormalizedResource, InfraBlueprint, IamStatement


def resolve(resources: list[NormalizedResource]) -> InfraBlueprint:
    """Resolve a list of NormalizedResource into an InfraBlueprint.

    - Detects VPC requirement from service types
    - Generates minimal IAM statements grouped by service
    - Collects unique services used
    """
    services_used: set[str] = set()
    vpc_required = False
    iam_by_service: dict[str, set[str]] = {}

    for res in resources:
        services_used.add(res.service)

        if res.service in VPC_REQUIRED_SERVICES:
            vpc_required = True

        actions = SERVICE_IAM_ACTIONS.get(res.service, [])
        if actions:
            iam_by_service.setdefault(res.service, set()).update(actions)

    # Build IAM statements — one per service for clarity
    iam_statements: list[IamStatement] = []
    for service in sorted(iam_by_service):
        iam_statements.append(IamStatement(
            effect="Allow",
            actions=sorted(iam_by_service[service]),
            resource="*",
        ))

    return InfraBlueprint(
        resources=resources,
        shared_iam_statements=iam_statements,
        vpc_required=vpc_required,
        services_used=services_used,
    )
