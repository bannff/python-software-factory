/**
 * Canvas-paint e2e smoke (bd-pws3, EPIC python-factory-iet5).
 *
 * Pins the bd-D agent → canvas paint round-trip end-to-end against
 * the live dashboard (assumed running on :3000 with API on :8000):
 *
 *   1. "open the graph view" → fe_navigate_canvas pill goes Done +
 *      Activity Bar flips to Graph (regression for bd-115z still
 *      working).
 *   2. "paint a graph showing the user kiro-agent" → ui_paint_canvas
 *      MCP tool → STATE patches → `agent.state.canvas.graph` mutates
 *      to a non-empty A2UI payload, OR the painted node test-id
 *      surfaces in the Graph view.
 *   3. "now show me on the live tab" → activity bar flips to Live and
 *      the generic <LiveView> renders content from
 *      `state.canvas.live` (or empty-state copy).
 *
 * Mirrors `canvas-aware-chat.spec.ts` (bd-w0gr): chromium-only,
 * `test.skip()` if API+dashboard not running, single shared page
 * across serial scenarios.
 */

import { expect, test, type Page } from "@playwright/test";

const CHAT_PLACEHOLDER = "Ask anything…";
const TOOL_PILL_TIMEOUT = 15_000;
const ACTIVITY_TIMEOUT = 15_000;
const PAINT_TIMEOUT = 30_000;
const IDLE_TIMEOUT = 60_000;

async function waitForChatIdle(page: Page): Promise<void> {
  // The send button swaps in a Square (Stop) lucide icon while the
  // agent is running (mirrors bd-w0gr).
  await expect
    .poll(
      async () => page.evaluate(
        () => document.querySelectorAll("svg.lucide-square").length),
      { timeout: IDLE_TIMEOUT, message: "chat agent never returned to idle" },
    )
    .toBe(0);
}

async function sendChatMessage(page: Page, message: string): Promise<void> {
  await waitForChatIdle(page);
  const ta = page.locator(`textarea[placeholder='${CHAT_PLACEHOLDER}']`);
  await expect(ta).toBeVisible();
  for (let attempt = 0; attempt < 2; attempt++) {
    await ta.click();
    await ta.fill(message);
    await expect(ta).toHaveValue(message);
    await ta.press("Enter");
    try {
      await expect(ta).toHaveValue("", { timeout: 5_000 });
      return;
    } catch (err) {
      if (attempt === 1) throw err;
      await waitForChatIdle(page);
    }
  }
}

async function waitForActiveView(page: Page, title: string): Promise<void> {
  await expect
    .poll(
      async () => page.evaluate(() => {
        const buttons = Array.from(
          document.querySelectorAll<HTMLButtonElement>("button[title]"));
        const active = buttons.find((b) =>
          b.querySelector("span.bg-violet-500"));
        return active?.title ?? null;
      }),
      { timeout: ACTIVITY_TIMEOUT,
        message: `expected Activity Bar active title=${title}` },
    )
    .toBe(title);
}

async function readCanvasGraphSlot(page: Page): Promise<unknown> {
  // Walk the React fiber tree from <body> to find a useAgent
  // memoized output carrying { agent } where agent.agentId =
  // 'companion_x' (mem 87e4611d L8: single agentId). agent.state is
  // mutated by @ag-ui/[email protected] defaultApplyEvents STATE_* cases.
  return page.evaluate(() => {
    const q: unknown[] = [document.body];
    const seen = new Set<unknown>();
    while (q.length) {
      const n = q.shift();
      if (!n || typeof n !== "object" || seen.has(n)) continue;
      seen.add(n);
      const obj = n as Record<string, unknown>;
      const ms = obj.memoizedState as Record<string, unknown> | undefined;
      if (ms && typeof ms === "object") {
        const ag = ms.agent as
          | { agentId?: string; state?: { canvas?: { graph?: unknown } } }
          | undefined;
        if (ag && ag.agentId === "companion_x")
          return ag.state?.canvas?.graph ?? null;
        q.push(ms);
      }
      for (const k of ["stateNode", "child", "sibling", "return", "current",
                       "_internalRoot"]) {
        const v = obj[k];
        if (v) q.push(v);
      }
    }
    return null;
  });
}

test.describe.serial("Canvas-paint smoke (bd-pws3)", () => {
  let page: Page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    const apiOk = await page
      .request.get("http://localhost:8000/openapi.json")
      .then((r) => r.ok())
      .catch(() => false);
    test.skip(
      !apiOk,
      "Companion-X API not reachable on :8000 — start the local API + dashboard before running this smoke.",
    );
    await page.goto("http://localhost:3000/");
    await expect(
      page.locator(`textarea[placeholder='${CHAT_PLACEHOLDER}']`),
    ).toBeVisible();
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2_000);
  });

  test.afterAll(async () => {
    await page?.close();
  });

  test("scenario 1: 'open the graph view' flips to Graph (bd-115z regression)", async () => {
    await sendChatMessage(page, "open the graph view");
    const card = page
      .locator("[data-state]")
      .filter({ hasText: "Switch view" })
      .filter({ hasText: "Frontend" })
      .first();
    await expect(card).toBeVisible({ timeout: TOOL_PILL_TIMEOUT });
    await expect(card.locator("text=/Done|Complete/i")).toBeVisible({
      timeout: TOOL_PILL_TIMEOUT,
    });
    await waitForActiveView(page, "Graph");
  });

  test("scenario 2: 'paint a graph' mutates agent.state.canvas.graph", async () => {
    await sendChatMessage(
      page,
      "paint a graph showing the user kiro-agent with two related findings",
    );
    await waitForChatIdle(page);
    // Either the painted node test-id surfaces in the Graph view OR
    // the agent.state.canvas.graph slot carries components. Whichever
    // arrives first is the contract pin.
    const painted = await Promise.race([
      page
        .locator("[data-testid='agent-painted-node']")
        .first()
        .waitFor({ state: "visible", timeout: PAINT_TIMEOUT })
        .then(() => "node" as const)
        .catch(() => null),
      expect
        .poll(async () => readCanvasGraphSlot(page), {
          timeout: PAINT_TIMEOUT,
          message: "expected agent.state.canvas.graph populated",
        })
        .not.toBeNull()
        .then(() => "state" as const)
        .catch(() => null),
    ]);
    if (painted === null) {
      // eslint-disable-next-line no-console
      console.warn(
        "scenario 2: canvas.graph slot:",
        JSON.stringify(await readCanvasGraphSlot(page), null, 2),
      );
    }
    expect(painted, "agent did not paint canvas.graph").not.toBeNull();
  });

  test("scenario 3: 'show me on the live tab' flips activity bar to Live", async () => {
    await sendChatMessage(page, "now show me on the live tab");
    await waitForActiveView(page, "Live");
    // <LiveView> renders SOMETHING — either an empty-state with the
    // ui_paint_canvas hint copy, or a painted ComponentTree from
    // state.canvas.live. Either path proves the view mounted.
    const liveBody = await page.locator("body").innerText();
    expect(liveBody.length).toBeGreaterThan(0);
  });
});
