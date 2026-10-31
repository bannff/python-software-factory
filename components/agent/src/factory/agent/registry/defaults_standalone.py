"""Standalone swarm presets — security-recon and code-review.

Extracted from defaults.py to keep the aggregator under 200 LOC.
"""
from __future__ import annotations

_SONNET = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

SECURITY_RECON_SWARM: dict = {
    "id": "security-recon",
    "name": "Security Recon Swarm",
    "description": (
        "Three-agent swarm: recon agent queries the graph tools for app topology, "
        "threat modeler runs STRIDE analysis, report writer summarizes."
    ),
    "entry_point": "recon-agent",
    "max_handoffs": 15,
    "max_iterations": 15,
    "agents": [
        {"id": "recon-agent", "model": "",
         "system_prompt": (
             "You are a security reconnaissance agent. Query the graph MCP tools "
             "to discover app topology, resources, IAM roles, and data flows. "
             "Summarize the attack surface and hand off to the threat modeler."
         ), "tools": ["read_file", "list_directory"]},
        {"id": "threat-modeler", "model": "",
         "system_prompt": (
             "You are a STRIDE threat modeling agent. Given an app's topology "
             "and attack surface, identify threats across Spoofing, Tampering, "
             "Repudiation, Information Disclosure, Denial of Service, and "
             "Elevation of Privilege. Rate each threat by severity."
         ), "tools": ["read_file"]},
        {"id": "report-writer", "model": "",
         "system_prompt": (
             "You are a security report writer. Compile findings from recon "
             "and threat modeling into a structured report with executive "
             "summary, findings table, and remediation recommendations."
         ), "tools": []},
    ],
}

CODE_REVIEW_SWARM: dict = {
    "id": "code-review",
    "name": "Code Review Swarm",
    "description": (
        "Two-agent swarm: static analysis agent scans code for vulnerabilities, "
        "dependency checker reviews third-party packages for known CVEs."
    ),
    "entry_point": "static-analyzer",
    "max_handoffs": 10,
    "max_iterations": 10,
    "agents": [
        {"id": "static-analyzer", "model": "",
         "system_prompt": (
             "You are a static code analysis agent. Read source files and "
             "identify security issues: injection flaws, auth bypasses, "
             "hardcoded secrets, insecure deserialization, SSRF, path traversal. "
             "Report each finding with severity, location, and remediation."
         ), "tools": ["read_file", "list_directory"]},
        {"id": "dependency-checker", "model": "",
         "system_prompt": (
             "You are a dependency security agent. Review package manifests "
             "(requirements.txt, package.json, pyproject.toml) for known "
             "vulnerable versions. Flag outdated or unmaintained packages."
         ), "tools": ["read_file", "list_directory"]},
    ],
}
