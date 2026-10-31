"""Import integrity scans production brick source only."""

from pathlib import Path

from factory.foreman.import_check import check_import_integrity


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_test_files_are_excluded_from_import_scan(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "components/demo/src/factory/demo/core.py",
        "import json\n",
    )
    _write(
        tmp_path,
        "components/demo/test/factory/demo/test_core.py",
        "import _foreman_missing_test_dependency_987654\n",
    )
    result = check_import_integrity(tmp_path)
    assert result["passed"] is True
    assert result["files_checked"] == 1


def test_component_and_base_source_are_scanned(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "components/demo/src/factory/demo/core.py",
        "import _foreman_missing_component_dependency_987654\n",
    )
    _write(
        tmp_path,
        "bases/demo/src/factory/demo/main.py",
        "import _foreman_missing_base_dependency_987654\n",
    )
    result = check_import_integrity(tmp_path)
    assert result["passed"] is False
    assert result["files_checked"] == 2
    assert result["total_unresolved"] == 2


def test_source_adapters_keep_optional_dependency_semantics(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "components/demo/src/factory/demo/core.py",
        "import json\n",
    )
    _write(
        tmp_path,
        "components/demo/src/factory/demo/runtime/adapters/external.py",
        "import _foreman_missing_optional_adapter_dependency_987654\n",
    )
    result = check_import_integrity(tmp_path)
    assert result["passed"] is True
    assert result["files_checked"] == 1
    assert result["adapters_skipped"] == 1
