# Sandbox secret mounts

Sandbox profiles may opt into the allowlisted `the offline-license secret` reference
using `secret_refs`. The Sandbox server resolves that name from its host-only
`SANDBOX_SECRET_DITTO_OFFLINE_LICENSE_FILE` configuration and bind-mounts the
regular file read-only at `/run/secrets/the offline-license secret`. Profiles cannot
provide a host path, a target path, or a writable mount. The host source path is
kept out of profile serialization, MCP inputs and results, runtime metadata,
events, and Sandbox logs.

Secret profiles must set `replace_existing: false`, use an existing local Docker
image ID in `sha256:<64 lowercase hex>` form, define `entrypoint` as fixed
nonempty Docker command arguments (for example, `[run]`), omit
`setup_commands`, and join a peer network explicitly marked `internal: true`.
A provision-time peer-network override is subject to the same requirement.
The local image ID and its baked Docker `Config.Entrypoint` are inspected before
any container or network mutation. Its entrypoint must be fixed argv with an
absolute noninteractive executable; a mutable tag, registry digest, missing image
entrypoint, or shell evaluation command is not accepted. The profile field
named `entrypoint` supplies arguments after the image in `docker run`; it does
not replace Docker's image entrypoint. Configure the baked command as a trusted
runner that performs the licensed workload itself. Sandbox does not accept
arbitrary `sandbox.execute` commands in secret-enabled environments, since any
command could read or exfiltrate the mounted file. If stored environment
metadata or the Docker marker says the container is secret-enabled, or Docker
cannot verify the marker, execution is denied before invoking the adapter.

Sandbox also omits submitted command text and output from execution telemetry
for secret-enabled or unverified containers. Runtime write, upload, download,
and diff APIs are disabled, and direct Docker adapter upload, download, and
listing fail closed when the secret marker cannot be verified. This prevents
file APIs from copying the license or a replacement executable through Sandbox.
Treat other workload egress and copied files as sensitive.

Configure the environment variable only in the trusted the control-plane runtime/Sandbox
server process. Do not put the path or license contents in Docker environment
variables, profile fields, setup commands, or experiment records. Secret mounts
are Docker-only; other Sandbox adapters do not support them.

The mount remains readable for the lifetime of the container. Removing the
container removes the bind mount, but read-only does not prevent a trusted
workload from copying readable license contents elsewhere in its container or
printing them through commands. Terminate disposable containers after each
licensed experiment, and treat their writable filesystem and outputs as
potentially sensitive. Sandbox does not promise secure erasure of copied data.

When an orphan sweep is invoked, it holds an exited secret-enabled container
for up to ten minutes after its verified Docker finish time so a trusted host
collector can copy exact allowlisted evidence files from the stopped container.
A missing or unverifiable finish time does not extend that hold. No production
sweep scheduler is wired in this repository, so the hold is not an automatic
deletion deadline. Collection must verify the container exit status and
artifact hashes, then explicitly terminate the container; a held or exited
container is not itself a passing experiment.
