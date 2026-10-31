"""Vuln-class configuration — maps vuln_class to CWE, OWASP, patterns.

Static orchestration config. The security brick owns the full CWE
taxonomy (30+ entries with parent/child hierarchy in Neo4j). This
dict is a lightweight pointer for graph parameterization.

Usage: caller passes context={"vuln_class": "IDOR"} and the graph
prompt, skill, CWE focus, and finding format all swap automatically.
"""
from __future__ import annotations

from typing import Any


VULN_CLASS_CONFIG: dict[str, dict[str, Any]] = {
    "IDOR": {
        "cwe": "CWE-639",
        "cwe_family": ["CWE-639", "CWE-284", "CWE-862", "CWE-915"],
        "owasp_ref": "WSTG-ATHZ-04",
        "owasp_name": "Testing for IDOR",
        "severity_default": "CRITICAL",
        "description": (
            "Insecure Direct Object Reference — user-controlled "
            "keys access other users' resources without authz."
        ),
        "code_patterns": [
            "Missing ownership check on CRUD operations",
            "User-controlled keys passed to DB without authz",
            "Endpoints accepting resource IDs without caller verification",
            "DAO/repository methods without customerId parameter",
            "Controller delegates to service without forwarding principal",
        ],
        "param_blocklist": [
            "marketplaceId", "locale", "language", "currency",
            "pageSize", "pageToken", "sortBy", "sortOrder",
            "format", "version", "apiVersion", "limit", "offset",
        ],
        "taint_sinks": [
            "repository.findById", "dao.get", "service.delete",
            "Model.objects.get", "db.query", "session.get",
        ],
    },
    "XSS": {
        "cwe": "CWE-79",
        "cwe_family": ["CWE-79"],
        "owasp_ref": "WSTG-INPV-01",
        "owasp_name": "Testing for Reflected XSS",
        "severity_default": "HIGH",
        "description": (
            "Cross-Site Scripting — unsanitized user input "
            "reflected or stored in HTML output."
        ),
        "code_patterns": [
            "Unsanitized output in HTML templates",
            "Direct string concatenation in response body",
            "Missing Content-Security-Policy headers",
            "innerHTML assignment from user input",
            "Template engines with autoescape disabled",
        ],
        "param_blocklist": ["pageSize", "sortBy", "format", "locale"],
        "taint_sinks": [
            "response.write", "innerHTML", "dangerouslySetInnerHTML",
            "render_template_string", "document.write", "eval",
        ],
    },
    "SQLi": {
        "cwe": "CWE-89",
        "cwe_family": ["CWE-89", "CWE-74"],
        "owasp_ref": "WSTG-INPV-05",
        "owasp_name": "Testing for SQL Injection",
        "severity_default": "CRITICAL",
        "description": (
            "SQL Injection — user input concatenated into "
            "SQL queries without parameterization."
        ),
        "code_patterns": [
            "String concatenation in SQL queries",
            "Missing parameterized queries / prepared statements",
            "ORM raw query methods with user input",
            "Dynamic table/column names from user input",
            "Stored procedures with EXEC + string concat",
        ],
        "param_blocklist": ["pageSize", "sortBy", "format", "locale"],
        "taint_sinks": [
            "cursor.execute", "Statement.execute", "connection.query",
            ".raw(", "executeQuery", "createNativeQuery",
        ],
    },
    "SSRF": {
        "cwe": "CWE-918",
        "cwe_family": ["CWE-918"],
        "owasp_ref": "WSTG-INPV-19",
        "owasp_name": "Testing for SSRF",
        "severity_default": "HIGH",
        "description": (
            "Server-Side Request Forgery — server fetches "
            "a URL controlled by the attacker."
        ),
        "code_patterns": [
            "URL parameters passed to HTTP client without validation",
            "Redirect endpoints following user-supplied URLs",
            "Image/file fetch from user-provided URLs",
            "Webhook URLs without allowlist validation",
            "DNS rebinding via user-controlled hostnames",
        ],
        "param_blocklist": ["pageSize", "format", "locale"],
        "taint_sinks": [
            "requests.get", "urllib.urlopen", "http.get",
            "fetch(", "HttpClient", "WebClient",
        ],
    },
    "CSRF": {
        "cwe": "CWE-352",
        "cwe_family": ["CWE-352"],
        "owasp_ref": "WSTG-SESS-05",
        "owasp_name": "Testing for CSRF",
        "severity_default": "MEDIUM",
        "description": (
            "Cross-Site Request Forgery — state-changing "
            "requests lack origin verification."
        ),
        "code_patterns": [
            "State-changing endpoints without CSRF token",
            "Missing SameSite cookie attribute",
            "No Origin/Referer header validation",
            "GET requests performing state changes",
            "CORS misconfiguration allowing cross-origin writes",
        ],
        "param_blocklist": [],
        "taint_sinks": [],  # CSRF is control-absence, not taint-flow
    },
    "Path_Traversal": {
        "cwe": "CWE-22",
        "cwe_family": ["CWE-22"],
        "owasp_ref": "WSTG-ATHZ-01",
        "owasp_name": "Testing for Path Traversal",
        "severity_default": "HIGH",
        "description": (
            "Path Traversal — user input used in file paths "
            "without proper sanitization."
        ),
        "code_patterns": [
            "File path constructed from user input without sanitization",
            "Missing canonicalization before path comparison",
            "Zip extraction without entry name validation (Zip Slip)",
            "Directory listing from user-controlled base path",
            "Symlink following without restriction",
        ],
        "param_blocklist": ["format", "locale", "encoding"],
        "taint_sinks": [
            "open(", "Path(", "os.path.join", "fs.readFile",
            "FileInputStream", "Files.read",
        ],
    },
}


def get_config(vuln_class: str) -> dict[str, Any]:
    """Get config for a vuln class. Raises KeyError if unknown."""
    return VULN_CLASS_CONFIG[vuln_class]


def supported_classes() -> list[str]:
    """Return all supported vuln class names."""
    return list(VULN_CLASS_CONFIG.keys())
