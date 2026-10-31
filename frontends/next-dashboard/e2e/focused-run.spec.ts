import { expect, test, type Page, type Route } from "@playwright/test";

const RUN_ID = "workflow-run-725-full-id";

/**
 * Per-tool fixture payloads, keyed by MCP tool name (bd:python-factory-736).
 *
 * Previously this mocked `**\/api/tools/**` REST bridge responses. The
 * bridge is retired — the dashboard now speaks real MCP `tools/call`
 * JSON-RPC over `/mcp`, so the mock intercepts JSON-RPC request bodies
 * instead of REST path segments.
 */
const TOOL_PAYLOADS: Record<string, unknown> = {
  graph_find_entities: { entities: [] },
  graph_get_stats: { node_count: 1, edge_count: 0 },
  graph_list_recent_runs: {
    runs: [{ run_id: RUN_ID, status: "completed", started_at: "2026-06-12T12:00:00Z" }],
  },
  graph_get_run_topology: {
    nodes: [{ id: RUN_ID, type: "WorkflowRun", properties: { run_id: RUN_ID } }],
    edges: [],
  },
  graph_get_tool_invocations_for_run: { rows: [], count: 0 },
  evals_get_run_result: { found: false, result: null },
  evals_get_dashboard_summary: { overview: {}, experiments: [] },
};

interface JsonRpcRequest {
  jsonrpc: "2.0";
  id?: number | string;
  method: string;
  params?: { name?: string; arguments?: Record<string, unknown> };
}

function jsonRpcResult(id: number | string | undefined, result: unknown) {
  return { jsonrpc: "2.0", id, result };
}

/** Build a `CallToolResult` carrying `data` as both structured and text content. */
function toolCallResult(data: unknown) {
  const envelope = { schema_version: "v1", ok: true, data };
  return {
    resultType: "complete",
    content: [{ type: "text", text: JSON.stringify(envelope) }],
    structuredContent: envelope,
    isError: false,
  };
}

async function mockFocusedRunApis(page: Page) {
  await page.route("**/mcp", async (route: Route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      // The transport's GET SSE probe — not needed for this scripted mock.
      await route.fulfill({ status: 405, body: "" });
      return;
    }
    let body: JsonRpcRequest;
    try {
      body = JSON.parse(request.postData() ?? "{}");
    } catch {
      await route.continue();
      return;
    }

    if (body.method === "server/discover") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(jsonRpcResult(body.id, {
          resultType: "complete",
          supportedVersions: ["2026-07-28"],
          capabilities: { tools: {} },
          ttlMs: 0,
          cacheScope: "private",
        })),
      });
      return;
    }
    if (body.method === "initialize") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(jsonRpcResult(body.id, {
          protocolVersion: "2024-11-05",
          capabilities: { tools: { listChanged: true } },
          serverInfo: { name: "companion-x-mock", version: "1.0.0" },
        })),
      });
      return;
    }
    if (body.method === "notifications/initialized") {
      await route.fulfill({ status: 202, body: "" });
      return;
    }
    if (body.method === "tools/call") {
      const toolName = body.params?.name ?? "";
      const payload = toolName === "get_tool_catalog"
        ? {
            tools: Object.keys(TOOL_PAYLOADS).map((name) => ({
              brick: name.startsWith("evals_") ? "evals" : "graph",
              name,
              qualified_name: name,
              description: name,
              input_schema: { type: "object" },
              category: "deterministic",
            })),
            aliases: {},
            bricks_loaded: ["graph", "evals"],
            bricks_failed: [],
            count: Object.keys(TOOL_PAYLOADS).length,
            categories: null,
          }
        : TOOL_PAYLOADS[toolName] ?? {};
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(jsonRpcResult(body.id, toolCallResult(payload))),
      });
      return;
    }
    // Any other JSON-RPC method (tools/list, ping, ...) — empty-ish default.
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(jsonRpcResult(body.id, {})),
    });
  });
}

async function expectFocus(page: Page) {
  await expect.poll(() => new URL(page.url()).searchParams.get("run")).toBe(RUN_ID);
  await expect(page.getByText(RUN_ID, { exact: true }).first()).toBeVisible();
  expect(new URL(page.url()).searchParams.get("theme")).toBe("dark");
}

test("focused run persists across Graph, Timeline, Metrics, and Evals", async ({ page }) => {
  const dashboardAvailable = await page.request.get("/").then((response) => response.ok()).catch(() => false);
  test.skip(!dashboardAvailable, "Companion-X dashboard is not running on :3000.");
  await mockFocusedRunApis(page);
  await page.goto("/?theme=dark");

  await page.getByTitle("Graph").click();
  await page.getByRole("button", { name: "Select a workflow run" }).click();
  await page.getByRole("button", { name: RUN_ID }).click();
  await expectFocus(page);

  const canvas = page.locator("canvas").first();
  await expect(canvas).toBeVisible();
  await page.waitForTimeout(2_000);
  const settledFrame = await canvas.screenshot();
  await page.waitForTimeout(500);
  expect(await canvas.screenshot(), "focused topology camera moved without explicit input").toEqual(settledFrame);

  for (const view of ["Timeline", "Metrics", "Evals"] as const) {
    await page.getByTitle(view).click();
    await expectFocus(page);
  }
  await expect(page.getByText(/No attributable eval artifact/i)).toBeVisible();
});
