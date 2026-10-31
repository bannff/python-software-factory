import { describe, expect, it } from "vitest";
import {
  Client,
  StreamableHTTPClientTransport,
} from "@modelcontextprotocol/client";

describe("modular MCP v2 wire", () => {
  it("auto-negotiates modern and lets the SDK drive confirmation retry", async () => {
    const requests: Array<Record<string, unknown>> = [];
    const transport = new StreamableHTTPClientTransport(
      new URL("http://test.local/mcp"),
      {
        fetch: async (_url, init) => {
          const request = JSON.parse(String(init?.body)) as {
            id: string | number;
            method: string;
            params?: Record<string, unknown>;
          };
          requests.push(request as unknown as Record<string, unknown>);
          let result: Record<string, unknown>;
          if (request.method === "server/discover") {
            result = {
              resultType: "complete",
              supportedVersions: ["2026-07-28"],
              capabilities: { tools: {} },
              ttlMs: 0,
              cacheScope: "private",
            };
          } else if (requests.filter((item) => item.method === "tools/call").length === 1) {
            result = {
              resultType: "input_required",
              inputRequests: {
                confirm: {
                  method: "elicitation/create",
                  params: {
                    mode: "form",
                    message: "Approve operation?",
                    requestedSchema: {
                      type: "object",
                      additionalProperties: false,
                      properties: { approved: { type: "boolean" } },
                      required: ["approved"],
                    },
                  },
                },
              },
            };
          } else {
            result = {
              resultType: "complete",
              content: [{ type: "text", text: "done" }],
              structuredContent: { schema_version: "v1", ok: true, data: { done: true } },
              isError: false,
            };
          }
          return new Response(JSON.stringify({ jsonrpc: "2.0", id: request.id, result }), {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        },
      },
    );
    const client = new Client(
      { name: "wire-test", version: "1.0.0" },
      {
        versionNegotiation: { mode: "auto" },
        capabilities: { elicitation: { form: {} } },
        inputRequired: { autoFulfill: true, maxRounds: 1 },
      },
    );
    client.setRequestHandler("elicitation/create", async () => ({
      action: "accept", content: { approved: true },
    }));

    await client.connect(transport);
    const result = await client.callTool({ name: "confirmable", arguments: { value: 1 } });
    await client.close();

    const calls = requests.filter((request) => request.method === "tools/call");
    expect(calls).toHaveLength(2);
    expect(calls[1].params).toMatchObject({
      inputResponses: { confirm: { action: "accept", content: { approved: true } } },
    });
    expect(result.structuredContent).toEqual({
      schema_version: "v1", ok: true, data: { done: true },
    });
  });
});
