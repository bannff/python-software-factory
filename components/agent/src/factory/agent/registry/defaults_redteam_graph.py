"""Red team graph defaults.

The internal recon/sandbox pipeline was removed with the recon
surface: its nested pipeline graph and the recon/pull-artifacts/
setup-sandbox swarms had no remaining public input. What survives is
the standalone DAST scan graph and the sandbox scan/prove swarms —
both run against LocalStack and take their context from the launch
request.
"""
from __future__ import annotations

from .defaults_redteam_exploit import PROVE_VULNS_SWARM, SCAN_VULNS_SWARM
from .defaults_redteam_idor import SCAN_IDOR_GRAPH

REDTEAM_SWARMS: list[dict] = [SCAN_VULNS_SWARM, PROVE_VULNS_SWARM]
REDTEAM_AGENTS: list[dict] = []
REDTEAM_GRAPHS: list[dict] = [SCAN_IDOR_GRAPH]
