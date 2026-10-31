// Chat & API Types

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: number;
  toolCalls?: ToolCall[];
}

export interface ToolCall {
  id: string;
  name: string;
  args: string;
  result?: string;
}

export interface ActiveToolCall extends ToolCall {
  active: boolean;
}

export interface Step {
  name: string;
  status: "running" | "completed" | "error";
  startedAt: number;
  finishedAt?: number;
}

export interface FrontendTool {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  frontend: true;
}

export interface RunAgentInput {
  threadId?: string;
  runId?: string;
  state?: Record<string, unknown>;
  messages: ChatMessage[];
  tools?: FrontendTool[];
}

// React Adapter / A2UI Types

export interface ReactAdapterNode {
  id: string;
  type: string;
  props: Record<string, unknown>;
  children?: ReactAdapterNode[];
  parent?: string;
}

export interface ReactAdapterView {
  id: string;
  name: string;
  brick: string;
  components: ReactAdapterNode[];
  metadata?: {
    nav_label?: string;
    nav_order?: number;
    [key: string]: unknown;
  };
}

// API Response Types

export interface ToolListResponse {
  tools: string[];
  count: number;
}

export interface ToolExecuteResponse {
  tool: string;
  result: unknown;
}

/**
 * A chat persona surfaced by GET /api/personas (bd:python-factory-d4roe.3).
 * Mirrors the agent brick's ``agent_get_agent_registry`` row shape
 * (``registry/agents.py::list_agents``). ``id`` is the opaque selector
 * the FE pushes into ``forwardedProps.companion_x_agent_id``.
 */
export interface Persona {
  id: string;
  name: string;
  description: string;
  model: string | null;
}

export interface PersonaListResponse {
  personas: Persona[];
  count: number;
}

export interface McpBrickHealth {
  healthy: boolean;
  error: string | null;
}

export interface McpHealthData {
  status: string;
  healthy_bricks: number;
  total_bricks: number;
  bricks: Record<string, McpBrickHealth>;
}

export interface TimelineCapabilities {
  live: {
    available: boolean;
    transport: string;
  };
  history: {
    available: boolean;
    persistent: boolean;
    backend: string;
    reason: string | null;
  };
}

export interface HealthResponse {
  gateway: string;
  status: "healthy" | "degraded" | "unhealthy" | "unknown";
  total_tools: number;
  mcp_health: McpHealthData;
  capabilities: {
    total_tools: number;
    registered_bricks: number;
    [key: string]: unknown;
  };
  timeline: TimelineCapabilities;
}
