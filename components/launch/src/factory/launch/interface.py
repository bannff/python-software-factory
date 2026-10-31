"""Polylith interface for launch brick.

Public surface: NCI protocol types + transport implementations + orchestrators +
probes + core resolver + platform-aware argv builder.
"""

from .runtime.nci.ports import NciCommand, NciTransport, to_wire
from .runtime.nci.udp import UdpNciTransport
from .runtime.nci.mock import MockNciTransport
from .runtime.nci.status import NciState, NciStatus, parse_status
from .runtime.nci.status_probe import GetStatusProbe
from .runtime.nci.version_probe import VersionProbe
from .runtime.orchestrator import LaunchOrchestrator, LaunchState, ReadinessProbe
from .runtime.process_orchestrator import ProcessLaunchOrchestrator
from .runtime.process_launcher import (
    ProcessLauncher,
    ProcessHandle,
    AsyncProcessLauncher,
    FakeProcessLauncher,
    FakeProcessHandle,
)
from .runtime.launch_command import (
    LaunchConfig,
    build_launch_argv,
    build_override_cfg_text,
    platform_launch_argv,
    is_darwin_trampoline,
)
from .runtime.core_resolver import resolve_core_path, DEFAULT_CORE_STEMS, default_cores_dir

__all__ = [
    "NciCommand",
    "NciTransport",
    "to_wire",
    "UdpNciTransport",
    "MockNciTransport",
    "NciState",
    "NciStatus",
    "parse_status",
    "GetStatusProbe",
    "VersionProbe",
    "LaunchOrchestrator",
    "LaunchState",
    "ReadinessProbe",
    "ProcessLaunchOrchestrator",
    "ProcessLauncher",
    "ProcessHandle",
    "AsyncProcessLauncher",
    "FakeProcessLauncher",
    "FakeProcessHandle",
    "LaunchConfig",
    "build_launch_argv",
    "build_override_cfg_text",
    "platform_launch_argv",
    "is_darwin_trampoline",
    "resolve_core_path",
    "DEFAULT_CORE_STEMS",
    "default_cores_dir",
]
