import { HttpAgent, type RunAgentInput } from "@ag-ui/client";
import {
  CopilotRuntime,
  createCopilotEndpoint,
} from "@copilotkit/runtime/v2";
import type { NextRequest } from "next/server";
import {
  requestLogger,
  responseLogger,
} from "@/lib/copilotkit/middleware/logging";
import { localMcpAuthorization } from "@/lib/mcp-local-credential";
import { COMPANION_X_AGENT_ID } from "@/lib/copilotkit/companion-agent";

/**
 * CopilotKit v2 runtime route.
 *
 * v2 ships a Hono-based endpoint that mounts handlers at:
 *   POST /agent/:agentId/run
 *   POST /agent/:agentId/connect
 *   POST /agent/:agentId/stop/:threadId
 *
 * v2's `<CopilotChat agentId="…">` calls those paths under whatever
 * `runtimeUrl` is configured on the provider — for us that's
 * `/api/copilotkit`. We expose a Next.js catch-all route at
 * `/api/copilotkit/[[...path]]` and delegate every method to the
 * Hono app, which speaks the standard `Request → Response` shape.
 *
 * The `HttpAgent` from `@ag-ui/client` speaks the AG-UI protocol
 * natively, so the Python `/ag-ui/run` SSE endpoint plugs straight
 * into the v2 runtime without any adapter glue.
 *
 * bd:python-factory-47sl — frontend cutover to CopilotKit v2.
 * bd:python-factory-sopw — agent ID imported from the shared module
 * (lib/copilotkit/companion-agent.ts) so the FE provider and this
 * server route never drift.
 *
 * bd-w5zk: middleware hooks wired via lib/copilotkit/middleware/logging.ts.
 * The 3 cross-cutting concerns the bd originally listed (OTel, cred-
 * refresh telemetry, memory auto-log) belong Python-side per
 * specialist verdicts — see bd-tq76, bd-5qs1, bd-sts6.
 */

const API_URL = process.env.API_URL || "http://localhost:8000";

/**
 * The local bearer is resolved on every run, not once at import: a token file
 * written after this module loaded (the launcher persists it on start) must be
 * picked up, and one removed by the launcher's cleanup must stop being sent.
 * When local auth is required and no credential resolves, the run fails
 * explicitly instead of going out unauthenticated and surfacing as an opaque
 * upstream 401.
 */
class LocalCredentialHttpAgent extends HttpAgent {
  protected requestInit(input: RunAgentInput): RequestInit {
    const init = super.requestInit(input);
    const { headers, missing } = localMcpAuthorization();
    if (missing) {
      throw new Error(
        "Local MCP credential is unavailable: start Companion X with "
        + "scripts/companion-x-ui.sh or set MCP_LOCAL_AUTH_TOKEN.",
      );
    }
    return { ...init, headers: { ...init.headers, ...headers } };
  }
}

const agent = new LocalCredentialHttpAgent({
  url: `${API_URL}/ag-ui/run`,
});

const runtime = new CopilotRuntime({
  agents: {
    [COMPANION_X_AGENT_ID]: agent,
  },
  beforeRequestMiddleware: requestLogger,
  afterRequestMiddleware: responseLogger,
});

const app = createCopilotEndpoint({
  runtime,
  basePath: "/api/copilotkit",
});

const handler = (req: NextRequest) => app.fetch(req);

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
export const PATCH = handler;
export const OPTIONS = handler;
export const HEAD = handler;

export const dynamic = "force-dynamic";
