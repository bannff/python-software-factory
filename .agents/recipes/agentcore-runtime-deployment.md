> **NOT IN USE ANYMORE.** This infra was torn down. The project is all-local now (see local the control-plane runtime dev steering). Kept for historical reference only — do not treat as current deployment guidance.

# AgentCore Runtime Deployment Recipe

Use this recipe for a containerized MCP server deployed to Amazon Bedrock AgentCore Runtime. Keep account IDs, ARNs, gateway IDs, secrets, and image URIs in deployment configuration or CI—not in this guide.

## Container contract

- Build from the repository root when the Dockerfile copies workspace-level files or sibling projects.
- Expose the port required by the runtime (commonly `8000`) and serve the configured MCP protocol, normally Streamable HTTP.
- Verify the image locally before publishing:

```bash
docker build -f path/to/Dockerfile .
```

## Safe image update

Prefer the control-plane API for an existing runtime when replacing an image:

1. Call `get_agent_runtime` and record the current runtime status and configuration.
2. Call `update_agent_runtime` with the existing role, network, protocol, authorization, and environment settings unchanged; modify only `containerUri`.
3. Poll `get_agent_runtime` until the runtime reaches its stable ready state.
4. If the update fails, inspect the prior runtime version before retrying.

This avoids accidentally dropping platform configuration such as observability, networking, authorization, or memory settings. Treat environment variables as configuration, not a place for secrets.

## Synchronize the gateway

An image update does not necessarily refresh a gateway’s cached MCP tool catalog. After the runtime is ready, call `synchronize_gateway_targets` for the runtime’s gateway target and poll the target until it is ready. Then verify the endpoint with an authenticated MCP `initialize` or health request.

## CLI caveat

If using the AgentCore CLI, confirm whether the command is performing an image deployment or a source/CodeBuild deployment. A Dockerfile that expects repository-root context can fail when the CLI packages only a project directory. Avoid configuration flags that disable platform observability or memory unless the change is intentional and reversible.

## Rollback and evidence

Record the previous image URI, runtime version, deployment result, gateway sync result, and health check. Roll back by pointing the runtime back to the previously known-good image through the same read-preserve-update-poll-sync sequence.
