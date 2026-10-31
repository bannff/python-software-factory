"""Versioned semantic identities for the ML CAN lifecycle."""

TRAIN_OPERATION = "ml.train-can-portfolio@v1"
ISSUE_OPERATION = "ml.issue-can-passports@v1"
CONFORM_OPERATION = "ml.run-can-cold-conformance@v1"
PROMOTE_OPERATION = "ml.promote-can-passports@v1"
PROJECT_OPERATION = "ml.project-can-pipeline-result@v1"

DATASET_BUNDLE_UNIT = "dataset.training-bundle@v1"
LIGHTGBM_UNIT = "lightgbm.train-can-id@v1"
PASSPORT_ISSUE_UNIT = "passport.issue@v1"
CONFORMANCE_UNIT = "passport.conformance@v1"
PASSPORT_PROMOTE_UNIT = "passport.promote@v1"

__all__ = [
    "CONFORMANCE_UNIT", "CONFORM_OPERATION", "DATASET_BUNDLE_UNIT",
    "ISSUE_OPERATION", "LIGHTGBM_UNIT", "PASSPORT_ISSUE_UNIT",
    "PASSPORT_PROMOTE_UNIT", "PROJECT_OPERATION", "PROMOTE_OPERATION",
    "TRAIN_OPERATION",
]
