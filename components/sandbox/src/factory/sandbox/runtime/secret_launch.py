"""Validation for fixed, noninteractive secret-enabled image launches."""
from __future__ import annotations
import re
from typing import Any
_LOCAL_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_INTERACTIVE_EXECUTABLES = {"sh", "bash", "dash", "ash", "zsh", "fish", "env"}

def validate_secret_launch(image: Any, command: Any) -> None:
    """Require a locally pinned image and fixed Docker CMD arguments."""
    if not isinstance(image, str) or _LOCAL_IMAGE_ID.fullmatch(image) is None:
        raise ValueError("Secret profiles require a local image ID (sha256:<64 hex>)")
    if command is None:
        raise ValueError("Secret profiles require a trusted fixed entrypoint")
    if not _safe_fixed_argv(command):
        raise ValueError("Secret profiles require fixed nonempty command args")
    if _uses_shell_or_eval(command):
        raise ValueError("Secret profiles require a fixed noninteractive command")
def validate_secret_image_entrypoint(entrypoint: Any) -> None:
    """Require an absolute, noninteractive executable baked into the pinned image."""
    if not _safe_fixed_argv(entrypoint) or not entrypoint[0].startswith("/"):
        raise ValueError("Secret mount requires a trusted fixed image ENTRYPOINT")
    if _uses_shell_or_eval(entrypoint):
        raise ValueError("Secret mount requires a trusted fixed image ENTRYPOINT")
def _safe_fixed_argv(argv: Any) -> bool:
    return isinstance(argv, (list, tuple)) and bool(argv) and all(
        isinstance(arg, str) and arg.strip() and arg == arg.strip()
        for arg in argv
    )
def _uses_shell_or_eval(argv: list[str] | tuple[str, ...]) -> bool:
    executable = argv[0].rsplit("/", 1)[-1]
    return executable in _INTERACTIVE_EXECUTABLES or any(
        arg in {"-c", "--eval"} for arg in argv
    )
