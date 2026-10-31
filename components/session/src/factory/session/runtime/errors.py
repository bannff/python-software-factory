"""Stable Session lifecycle failure types."""


class SessionIdentityError(PermissionError):
    pass


class SessionNotFoundError(LookupError):
    pass


class SessionConflictError(RuntimeError):
    pass


class SendIdRejectedError(ValueError):
    pass


class SessionBindingRejectedError(ValueError):
    pass


class SessionProjectRejectedError(ValueError):
    """The requested ``project`` path was refused by devtools' own path
    validation (outside ``COMPANION_X_PROJECT_ALLOWED_ROOTS``). Session-
    owned twin of ``devtools``' ``PathRefused`` — translated at the single
    call site in ``lifecycle.py::create()`` rather than importing that
    brick-internal exception type across the boundary (bd: found live
    2026-09-16, row 17 cycle — this used to propagate `PathRefused`
    uncaught, flattening to a generic ``tool_execution_failed`` that hid
    the real cause from both the FE and from live debugging)."""


__all__ = [
    "SendIdRejectedError", "SessionBindingRejectedError", "SessionConflictError",
    "SessionIdentityError", "SessionNotFoundError", "SessionProjectRejectedError",
]
