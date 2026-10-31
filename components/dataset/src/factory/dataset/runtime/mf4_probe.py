"""Shared raw MF4 CAN-frame iteration and observed fingerprint probing."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .dbc_models import MessageFingerprint
from .mf4_source import open_mf4_stream


def iter_mf4_can_samples(path: Path) -> Iterator[tuple[Any, int, str]]:
    """Yield structured CAN_DataFrame samples without requiring a DBC."""
    from asammdf import MDF

    with open_mf4_stream(path) as stream:
        try:
            mdf = MDF(stream, read_only=True)
        except Exception as error:
            raise ValueError(f"Failed to open MF4 file {path}: {error}") from error
        try:
            for group_index, group in enumerate(mdf.groups):
                names = {channel.name for channel in group.channels}
                if "CAN_DataFrame" not in names or "Timestamp" not in names:
                    continue
                if any(name.startswith(("CAN_ErrorFrame", "CAN_RemoteFrame"))
                       for name in names):
                    continue
                try:
                    parent, timestamp = _get_can_signals(mdf, group, group_index)
                    samples = parent.samples
                except Exception:
                    continue
                if not hasattr(samples, "dtype") or not len(samples):
                    continue
                timestamps_ns = (timestamp.samples * 1_000_000).astype("int64")
                for index, sample in enumerate(samples):
                    yield sample, int(timestamps_ns[index]), path.stem
        finally:
            mdf.close()


def _get_can_signals(mdf: Any, group: Any, group_index: int) -> tuple[Any, Any]:
    """Prefer name/group lookup; retain compatibility with index-required readers."""
    try:
        return (
            mdf.get("CAN_DataFrame", group=group_index),
            mdf.get("Timestamp", group=group_index),
        )
    except TypeError:
        positions = {channel.name: index for index, channel in enumerate(group.channels)}
        return (
            mdf.get("CAN_DataFrame", group=group_index,
                    index=positions["CAN_DataFrame"]),
            mdf.get("Timestamp", group=group_index, index=positions["Timestamp"]),
        )


def probe_mf4_fingerprints(paths: tuple[Path, ...]) -> tuple[MessageFingerprint, ...]:
    """Derive exact observed arbitration-ID/DLC/IDE tuples from source bytes."""
    observed = {
        MessageFingerprint(
            arbitration_id=int(sample["CAN_DataFrame.ID"]),
            dlc=int(sample["CAN_DataFrame.DLC"]),
            is_extended=bool(int(sample["CAN_DataFrame.IDE"])),
        )
        for path in paths
        for sample, _, _ in iter_mf4_can_samples(path)
    }
    if not observed:
        raise ValueError("MF4 sources contain no CAN_DataFrame observations")
    return tuple(sorted(observed, key=lambda item: (
        item.arbitration_id, item.dlc, item.is_extended,
    )))


__all__ = ["iter_mf4_can_samples", "probe_mf4_fingerprints"]
