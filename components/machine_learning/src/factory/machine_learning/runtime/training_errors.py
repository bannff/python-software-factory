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
    if "no module named" in text or isinstance(error, ModuleNotFoundError):
        return "native_dependency_missing"
    if isinstance(error, OSError):
        return "training_data_unreadable"
    return "training_failed"
