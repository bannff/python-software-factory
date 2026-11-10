"""Map training exceptions to a short, safe public code.

``ml_train_timeseries`` used to collapse server configuration problems and bad
data into one opaque failure, so a UI could only say "check your data". The
classes below are the user-actionable causes; everything else stays generic.
Matching is on the exception text of our own composition code, never on user
input, and only the code (not the text) is returned.
"""
from __future__ import annotations


def classify_training_error(error: BaseException) -> str:
    text = str(error).lower()
    if "model_root" in text or "ml_lightgbm_model_root" in text:
        return "model_root_not_configured"
    if "symlink" in text:
        return "symlink_path_rejected"
    if "not exact binary tabular data" in text:
        # LightGBM needs X 2-D, y strictly 0/1, as .npy or .parquet; the log has the detail.
        return "training_data_shape_invalid"
    if "no module named" in text or isinstance(error, ModuleNotFoundError):
        return "native_dependency_missing"
    if isinstance(error, OSError):
        return "training_data_unreadable"
    return "training_failed"


def training_error_message(code: str, error: BaseException) -> str:
    """Public message: a missing library names the group that installs it."""
    if code != "native_dependency_missing":
        return str(error)
    from .training_libs import INSTALL_HINT
    return f"{error}. ML training libraries are not installed; run: {INSTALL_HINT}"
