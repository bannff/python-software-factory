"""Packaged default sandbox profiles (shipped with the brick).

This is a *data* subpackage: it holds ``<name>.yaml`` profile files that are
always present regardless of ``SANDBOX_PROFILES_DIR``. The ``__init__`` marker
makes the directory an importable package so the YAML files are guaranteed to
ship inside an installed wheel and are readable via ``importlib.resources``
(never by filesystem path).
"""
