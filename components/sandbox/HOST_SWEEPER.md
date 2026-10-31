# Host Sandbox sweeper

`factory.sandbox.runtime.host_sweep` is a one-shot host process. A macOS
LaunchAgent can invoke it every 60 seconds using the template in
`ops/com.ditto.factory-sandbox-sweep.plist.template`. Render its three
placeholders to absolute paths before loading it: a Python interpreter with
the Sandbox dependencies, `components/sandbox/src`, and the same
`SANDBOX_TMP_ROOT` used by the collector. Run the LaunchAgent as the same user
that owns the Docker daemon connection and collector lock directory. The
template is not installed automatically.

Before installation, run a non-mutating host preflight with the template's
`PATH` and the rendered Python/PYTHONPATH:

```sh
PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin \
PYTHONPATH=<absolute-components-sandbox-src> \
<absolute-python-bin> -m factory.sandbox.runtime.host_sweep --check
```

The sweep reads only Docker container status and labels. It selects full
64-character IDs with `factory.sandbox=true`, waits 600 seconds after a verified
exit for secret-enabled containers, then acquires the collector's per-container
`flock` before removal. A collector lock held at
`$SANDBOX_TMP_ROOT/collector-locks/<id>.lock` postpones removal. Lock files
remain on disk to avoid inode races. A failed or unverifiable lock state also
postpones removal. After successful container removal, an empty, Sandbox-owned
peer bridge is removed. This process does not inspect or copy evidence, logs,
or secrets.

New secret-enabled containers require auto-termination and carry a validated
`factory.sandbox.timeout_seconds` label (60–86,400 seconds, default 3,600).
The sweep removes a running secret container only when that label and Docker's
`StartedAt` establish that the runtime has expired. Older running containers
without a valid label or verified start time are left for explicit termination.
The sweeper rechecks Docker state and structured labels after acquiring the
collector lock. It skips an exited secret container whose `FinishedAt` cannot
be verified. Empty owned bridges are retried on later sweeps after a 120-second
grace period, covering transient Docker removal failures without racing a new
peer provision.
Host-only invocation does not have the MCP event service registry;
workload reap events are best-effort only when sweeping through the Sandbox
runtime process.
