"""Hardened isolated-process ModelPassport conformance runner."""
from __future__ import annotations

import json
import math
import os
import secrets
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from .sealed_probe_store import SealedProbeStore
from ..model_passport import ConformanceEvidence, ModelPassport
from ..passport_evidence import derive_conformance_evidence
from ..passport_probe_contracts import PassportProbeInput, PassportProbeResult
from ..passport_snapshot import verified_snapshot
from ..passport_store_models import ModelPassportRef
from ..passport_validation import canonical_json

_MAX_INPUT = 131_072
_MAX_OUTPUT = 65_536


class LocalCanModelConformanceRunner:
    """Snapshot and probe an exact approved CAN candidate in a fresh interpreter."""

    def __init__(self, storage_root: str | Path, timeout_seconds: float = 60.0) -> None:
        self._root = Path(storage_root).expanduser().absolute()
        self._timeout = timeout_seconds
        self._evidence = SealedProbeStore(self._root)

    def run(
        self, candidate: ModelPassport, ref: ModelPassportRef, *,
        effect_id: str | None = None,
    ) -> ConformanceEvidence:
        nonce = effect_id if effect_id is not None else secrets.token_hex(16)
        roles = ["model", "feature_contract", "prepared_x", "prepared_y"]
        if candidate.inference.loader == "ncps.torch.LTC.state_dict":
            roles.append("prepared_timespans")
        with verified_snapshot(candidate, self._root, tuple(roles)) as snapshot:
            payload = PassportProbeInput(
                passport=candidate, snapshot_root=str(snapshot["root"]),
                model_path=str(snapshot["model"]),
                contract_path=str(snapshot["feature_contract"]),
                prepared_x_path=str(snapshot["prepared_x"]),
                prepared_y_path=str(snapshot["prepared_y"]),
                prepared_timespans_path=(
                    str(snapshot["prepared_timespans"])
                    if "prepared_timespans" in snapshot else None
                ),
                nonce=nonce,
            )
            result = self._execute(payload)
        artifact = self._evidence.publish(result)
        return derive_conformance_evidence(
            candidate=candidate, nonce=nonce, artifact=artifact, store=self._evidence,
            evaluation_pointers=candidate.evaluation_pointers,
            reject_current_pid=True,
        )

    def _execute(self, payload: PassportProbeInput) -> PassportProbeResult:
        raw = canonical_json(payload.model_dump(mode="json"))
        if len(raw) > _MAX_INPUT:
            raise ValueError("fresh CAN model conformance input exceeded limit")
        with tempfile.TemporaryDirectory(prefix="ml-passport-probe-") as work:
            private = Path(work)
            os.chmod(private, 0o700)
            stdout_path, stderr_path = private / "stdout", private / "stderr"
            with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
                process = subprocess.Popen(
                    [sys.executable, "-I", "-m",
                     "factory.machine_learning.runtime.passport_probe"],
                    stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                    cwd=Path(sys.executable).resolve().parent,
                    env=self._environment(private), close_fds=True,
                    start_new_session=True, preexec_fn=self._limits,
                )
                try:
                    process.communicate(input=raw, timeout=self._timeout)
                except subprocess.TimeoutExpired as exc:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise ValueError("fresh CAN model conformance timed out") from exc
            if process.returncode != 0:
                raise ValueError("fresh CAN model conformance failed")
            if stdout_path.stat().st_size > _MAX_OUTPUT or stderr_path.stat().st_size:
                raise ValueError("fresh CAN model conformance returned invalid output")
            try:
                document = json.loads(stdout_path.read_bytes())
                return PassportProbeResult.model_validate(document)
            except Exception as exc:
                raise ValueError("fresh CAN model conformance returned invalid output") from exc

    def _limits(self) -> None:
        try:
            import resource
            cpu = max(1, math.ceil(self._timeout) + 1)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
            resource.setrlimit(resource.RLIMIT_FSIZE, (_MAX_OUTPUT, _MAX_OUTPUT))
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        except (ImportError, OSError, ValueError):
            pass
        os.umask(0o077)

    @staticmethod
    def _environment(tempdir: Path) -> dict[str, str]:
        return {
            "TMPDIR": str(tempdir), "LANG": "C", "LC_ALL": "C",
            "PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
            "HF_HUB_DISABLE_PROGRESS_BARS": "1", "TRANSFORMERS_VERBOSITY": "error",
        }


LocalLightGBMConformanceRunner = LocalCanModelConformanceRunner

__all__ = ["LocalCanModelConformanceRunner", "LocalLightGBMConformanceRunner"]
