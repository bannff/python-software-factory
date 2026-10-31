# Sandbox peer networks

Profiles can opt separate Sandbox containers into a shared, user-defined Docker
bridge. The bridge gives each container a stable DNS name so peer software can
connect without host port publication or hard-coded container IPs.

```yaml
image: edge-lab:latest
container_name: edge-peer
replace_existing: false
peer_network:
  network_id: edge-lab-demo
  alias: edge-peer-a
  port: 24225
  internal: true
```

Create another environment from a profile with the same `network_id`, a
different `alias`, and the same or different listener port as its service
requires. The peer process must bind the configured port to `0.0.0.0` inside
its container. Sandbox returns the stable endpoint as `alias:port` in
environment metadata and status. It does not publish that port on the host.

Sandbox creates a bridge named `factory-sandbox-<network_id>` and labels it as
Sandbox-owned. Existing networks with that name are reused only when they carry
the ownership label and have the requested internal mode. `internal: true`
creates the bridge with Docker's `--internal` option, removing its normal
external routing/NAT while retaining container-to-container DNS and TCP on that
bridge. Internal peer networks reject profiles with host-published port
mappings. Omit it or set it to `false` when peers need normal external routing
or host-published service ports.
When a peer is terminated, Sandbox removes the bridge only after Docker reports
it empty and Sandbox-owned; Docker rejects a concurrent remove if another peer
attaches in the meantime. Legacy profiles without `peer_network` keep their
existing isolated networking behavior.

The network ID is a lowercase DNS slug, aliases are lowercase DNS names, and
ports must be in the TCP/UDP port range. Device presets remain Linux resource
proxies; a Docker bridge provides peer reachability, not iOS/Android runtime or
radio emulation. The internal setting configures Docker's network isolation;
Sandbox also rejects an alias already attached to another container on the
bridge; replacing the same named container may reuse its alias. This contract
test does not prove peer DNS/TCP reachability or absence of WAN access in a live
host environment. Do not place credentials in network names, aliases, or
profile metadata.

Alias uniqueness is checked against the Docker daemon immediately before
provisioning. Sandbox currently supports one active provisioner process per
Docker daemon; concurrent requests through that process are serialized.
Running multiple Sandbox server processes against the same daemon is
unsupported because alias inspection and container creation are not an atomic
Docker operation.

## Live Docker check (2026-09-30)

The current Sandbox runtime provisioned an `iphone-15` and a `pixel-8` Linux
proxy from the `edge-lab` image on one disposable internal bridge
(`eng197-live-29df66c49a`). Docker reported image platform `linux/arm64`, two
CPUs and 2,048 MiB per peer, no published host ports, two attached containers,
and the Sandbox ownership label. Both peers resolved the other's declared DNS
alias and opened TCP port 24225 in both directions. Both returned
`connect_ex=101` for the predeclared public-IP canary `1.1.1.1:443` on that
bridge. Runtime list and status both reported the configured alias endpoints
and Linux proxy preset identities, and Docker labels matched both selected
presets. Termination removed both containers and the empty owned bridge. The evidence
was captured in `/private/tmp/eng197-live-peer-network-evidence.json` on the
lab host and summarized in the internal tracker.

This was a network transport check using local Python HTTP listeners. It did
not run the Ditto SDK or prove application-level peer sync. The running
the control-plane runtime MCP process still advertises the prior Sandbox provision schema;
the live check called the current Sandbox runtime directly. Restart that MCP
process and verify its `device_preset`/`peer_network` tool fields before using
the new provisioning contract through MCP.
