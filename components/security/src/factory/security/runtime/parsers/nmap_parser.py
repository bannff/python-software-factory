"""Parse Nmap XML output into standardized finding dicts."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


def parse(raw_output: str) -> list[dict[str, Any]]:
    """Parse nmap -oX XML output into finding dicts.

    Returns empty list on malformed input — never raises.
    """
    if not raw_output or not raw_output.strip():
        return []
    try:
        root = ET.fromstring(raw_output)
    except ET.ParseError:
        return []

    findings: list[dict[str, Any]] = []
    for host in root.findall(".//host"):
        addr_el = host.find("address")
        addr = addr_el.get("addr", "unknown") if addr_el is not None else "unknown"

        for port_el in host.findall(".//port"):
            proto = port_el.get("protocol", "tcp")
            portid = port_el.get("portid", "0")
            state_el = port_el.find("state")
            state = state_el.get("state", "unknown") if state_el is not None else "unknown"
            if state != "open":
                continue

            svc_el = port_el.find("service")
            svc_name = svc_el.get("name", "") if svc_el is not None else ""
            svc_product = svc_el.get("product", "") if svc_el is not None else ""
            svc_version = svc_el.get("version", "") if svc_el is not None else ""

            svc_desc = " ".join(filter(None, [svc_product, svc_version])) or svc_name
            findings.append({
                "title": f"Open port {portid}/{proto} ({svc_name})",
                "severity": "info",
                "cwe": "CWE-200",
                "description": f"Service: {svc_desc}" if svc_desc else "Open port detected",
                "location": f"{addr}:{portid}/{proto}",
                "evidence": f"state=open service={svc_name} product={svc_product} version={svc_version}",
            })

    return findings
