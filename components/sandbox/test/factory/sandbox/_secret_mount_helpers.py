"""Shared constants for the secret-mount test modules."""

from __future__ import annotations

PINNED_IMAGE = "sha256:" + "a" * 64
INSPECTED_ENTRYPOINT = '["/usr/local/bin/python", "/sealed/entrypoint.py"]\n'
