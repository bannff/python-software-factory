# edge-lab

`edge-lab` is a Linux workload image and Sandbox profile for rehearsing the
`edge-ditto-device-flow-001` experiment. Its image contains Python 3.12 and a
hash-locked Ditto Python SDK preview wheel. It contains no license, model,
dataset, or experiment results.

Build from this directory:

```sh
docker build -t python-factory/edge-lab:local .
```

Set `SANDBOX_ADAPTER=docker` and point `SANDBOX_PROFILES_DIR` at the absolute
`projects/the control-plane project/sandbox-profiles` directory in the MCP server's
environment. Until this branch's Sandbox code is installed in the server's
Python environment, also put this worktree's `components/sandbox/src` first
on `PYTHONPATH` so the device-preset tools and profile fields are recognized.
Restart that server, call `sandbox.list_device_presets`, then provision the
workload with a target, for example
`sandbox.provision(profile="edge-lab", device_preset="iphone-15")`.
The same image can be used with `ipad-a16`, `pixel-8`, `galaxy-s24`,
`galaxy-tab-s9`, `zebra-tc58`, or `raspberry-pi-5-4gb`. Presets are packaged
with Sandbox; additional validated YAML presets can be placed in the directory
set by `SANDBOX_DEVICE_PRESETS_DIR`. The older call without a device preset
still provisions the generic `edge-lab` container and refuses to replace it.
Selected presets create uniquely named containers and also refuse to replace
an existing container. Selected presets require a profile without fixed host
ports; `edge-lab` has none. Use `sandbox.upload_file` and `sandbox.execute` for each
environment; call `sandbox.terminate(env_id=...)` when finished.

Sandbox profiles describe the workload image and tools; device presets describe
the intended form factor and a repeatable **Linux proxy** CPU/memory envelope.
The preset limits are initial experiment budgets, not manufacturer RAM/CPU
specifications or measured app limits. They do not run iOS or Android or
reproduce a device SoC, accelerator, radios, energy use, or thermal behavior.
Reprovision after changing YAML; an already running container keeps its old
settings. Record the requested preset and `docker inspect` image, platform,
CPU quota, and memory limit in each run's evidence. A physical-device run is
required before claiming device performance or mesh-radio behavior.

These instructions target the the control-plane runtime MCP server running directly on the
host. The separate the control-plane runtime Compose security overlay selects LocalStack
and does not mount this profile directory; it does not use this setup.

The first Ditto flow protocol launches N independent processes inside one
container. The preset path can launch multiple containers for stronger process
and filesystem isolation. Every SDK instance needs its own persistence
directory and port; peers share one test database ID. The containers do not
establish a Ditto mesh topology on their own. Supply the
authorized offline Ditto license at run time through a protected local input.
Do not put it in this profile, Dockerfile, command history, or checked-in
artifacts. Model and dataset artifacts are uploaded for a run and identified
by hash in its manifest. The run output belongs in artifact storage, with
curated evidence linked from the experiment's `run-index.json`.

This setup can assess local writes, persistence, and TCP peer sync on Linux.
It cannot establish iPhone resource behavior or independent device network
conditions. Those are separate experiment stages.
