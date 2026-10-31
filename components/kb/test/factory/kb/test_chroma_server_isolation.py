"""Guardrail: ChromaDB server mode stays isolated to its opt-in adapter.

chromadb <= 1.5.9 carries critical advisories with NO patched release:

- CVE-2026-45833  code injection
- CVE-2026-45829  pre-authentication code injection
- CVE-2026-45830  cross-tenant read/write by any authenticated user
- CVE-2026-45831  SimpleRBAC ignores tenant/db/collection scope

Three of the four are server-mode / authorization issues. The embedded
``PersistentClient`` used by the default adapters (kb ``chroma``, memory
``amem``) has no network, no auth and no tenants, so those paths are not
reachable in embedded use. This guardrail keeps the risky
``chromadb.HttpClient`` construction confined to the explicitly opt-in
``chroma_server`` adapter so it cannot creep into a default path.

Real fix: M7.7 (memory + KB onto one networkx graph).
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[5]
_ALLOWED = "chroma_server.py"


def test_chromadb_http_client_is_confined_to_the_server_adapter() -> None:
    offenders: list[str] = []
    for group in ("components", "bases"):
        for path in (_ROOT / group).glob("*/src/**/*.py"):
            if path.name == _ALLOWED:
                continue
            if "chromadb.HttpClient" in path.read_text():
                offenders.append(str(path.relative_to(_ROOT)))
    assert offenders == [], (
        "chromadb.HttpClient must stay inside the opt-in chroma_server adapter "
        f"(server mode exposes CVE-2026-45829/45830/45831): {offenders}"
    )
