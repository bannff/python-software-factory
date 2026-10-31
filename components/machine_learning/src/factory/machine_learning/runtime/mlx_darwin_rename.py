"""Darwin no-replace publication primitive for sealed MLX references."""
from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path

_RENAME_EXCL, _AT_FDCWD = 0x00000004, -2


def rename_exclusive(source: Path, destination: Path) -> None:
    """Atomically rename without replacement on Darwin."""
    if os.uname().sysname != "Darwin":
        raise OSError(errno.ENOTSUP, "exclusive MLX ref publication requires renameatx_np")
    function = ctypes.CDLL(None, use_errno=True).renameatx_np
    function.argtypes = [
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint,
    ]
    result = function(
        _AT_FDCWD, os.fsencode(source), _AT_FDCWD, os.fsencode(destination),
        _RENAME_EXCL,
    )
    if result:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise FileExistsError(error, os.strerror(error), destination)
        raise OSError(error, os.strerror(error), destination)


__all__ = ["rename_exclusive"]
