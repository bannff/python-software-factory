export function deriveGraphNodeDisplayName(
  id: string,
  type: string,
  properties: Record<string, unknown> | undefined,
): string {
  const props = properties ?? {};

  if (typeof props.name === "string" && props.name !== "") return props.name;
  if (typeof props.tool_name === "string" && props.tool_name !== "") return props.tool_name;
  if (typeof props.brick_name === "string" && props.brick_name !== "") return props.brick_name;
  if (typeof props.agent_id === "string" && props.agent_id !== "") return `agent:${props.agent_id}`;
  if (typeof props.principal_id === "string" && props.principal_id !== "") return `user:${props.principal_id}`;
  if (typeof props.workflow_run_id === "string" && props.workflow_run_id !== "") {
    return `run:${String(props.workflow_run_id).slice(0, 8)}`;
  }
  if (type === "memory" && typeof props.content === "string" && props.content !== "") {
    return props.content.length > 48 ? `${props.content.slice(0, 48)}…` : props.content;
  }
  if (type === "Session" && id.startsWith("session-")) {
    return `session:${id.slice("session-".length, "session-".length + 8)}`;
  }
  if (type === "ToolInvocation" && id.startsWith("tool-inv-")) {
    return `tool:${id.slice("tool-inv-".length, "tool-inv-".length + 8)}`;
  }
  return id;
}