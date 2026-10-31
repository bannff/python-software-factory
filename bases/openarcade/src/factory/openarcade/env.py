"""Environment-variable contract for OpenArcade base.

Priority: explicit CLI value > env var > CWD-relative default.
Never call Path.home() or expanduser() — the base is a kiosk, not a desktop app.
"""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path

DEFAULT_CONFIG_DIR = Path("./openarcade_config")
DEFAULT_NCI_HOST = "127.0.0.1"
DEFAULT_NCI_PORT = 55355

_BLOCKED_NCI_NETS = (
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
)

_SCAN_MAX_REPORT_BYTES = 4 * 1024 * 1024
_SCAN_BLOCKED_PREFIXES = ("/proc", "/sys", "/dev")


def _is_blocked_scan_path(path: Path) -> str | None:
    resolved = path.resolve()
    for prefix in _SCAN_BLOCKED_PREFIXES:
        candidate = Path(prefix).resolve()
        if resolved == candidate or candidate in resolved.parents:
            return prefix
    return None


def validate_scan_dir(path: Path) -> None:
    """Reject paths under system directories the scanner must not enter.

    The path must be a directory that exists. Used by ``openarcade_scan_roms``.
    """
    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")
    blocked = _is_blocked_scan_path(path)
    if blocked:
        raise ValueError(
            f"Scanning {blocked} is not allowed (refused: {path})"
        )


def validate_readable_file(path: Path) -> None:
    """Reject paths under system directories and non-files. Used by
    ``openarcade_check_compatibility``.
    """
    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
    blocked = _is_blocked_scan_path(path)
    if blocked:
        raise ValueError(
            f"Reading from {blocked} is not allowed (refused: {path})"
        )


# Back-compat alias for the old name; new code should call validate_scan_dir.
def validate_scan_path(path: Path) -> None:  # noqa: D401
    """Deprecated: use ``validate_scan_dir`` or ``validate_readable_file``."""
    return validate_scan_dir(path)


def resolve_config_dir(cli_value: str | os.PathLike[str] | None) -> Path:
    """Return the config dir to use, in priority order:

    1. ``cli_value`` (from ``--config-dir``)
    2. ``$OPENARCADE_CONFIG_DIR``
    3. CWD-relative ``./openarcade_config``

    Refuses to resolve under ``$HOME`` to keep the kiosk's config out of the
    operator's home dir. Raises ``ValueError`` if the resolved path would land
    there.
    """
    if cli_value is not None:
        chosen = Path(cli_value)
    else:
        env_value = os.environ.get("OPENARCADE_CONFIG_DIR")
        chosen = Path(env_value) if env_value else DEFAULT_CONFIG_DIR
    resolved = chosen.resolve()
    home = Path(os.environ.get("HOME", "/nonexistent")).resolve()
    if home in resolved.parents or resolved == home:
        raise ValueError(
            f"OpenArcade config dir must not live under $HOME: got {resolved}"
        )
    return resolved


def _validate_nci_host(host: str) -> str:
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return host
    for net in _BLOCKED_NCI_NETS:
        if addr in net:
            raise ValueError(
                f"NCI host {host} is in a blocked range ({net}); "
                "refusing to send commands to link-local targets"
            )
    return host


def resolve_nci_target(
    cli_host: str | None, cli_port: int | None
) -> tuple[str, int]:
    """Return the NCI UDP target as ``(host, port)``.

    Priority: CLI flags > env vars > defaults (``127.0.0.1:55355``).

    Refuses link-local targets (IPv4 169.254/16 and IPv6 fe80::/10) to
    prevent SSRF against the AWS instance metadata service
    (``169.254.169.254``) and IPv6 link-local. Loopback (``127.0.0.1``) and
    RFC1918 private ranges are allowed because the legitimate use case is
    a local or LAN-attached RetroArch.
    """
    host = cli_host or os.environ.get("OPENARCADE_NCI_HOST") or DEFAULT_NCI_HOST
    port_raw = (
        cli_port
        if cli_port is not None
        else os.environ.get("OPENARCADE_NCI_PORT") or str(DEFAULT_NCI_PORT)
    )
    try:
        port = int(port_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"OPENARCADE_NCI_PORT must be an integer, got {port_raw!r}"
        ) from exc
    if not (0 < port < 65536):
        raise ValueError(f"NCI port out of range: {port}")
    return _validate_nci_host(host), port
