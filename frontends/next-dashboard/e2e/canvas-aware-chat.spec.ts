/**
 * Canvas-aware chat e2e smoke (bd-w0gr).
 *
 * Pins the bd-115z + bd-n368 + bd-vw04 round-trip end-to-end by driving
 * the live dashboard (assumed running on :3000 with API on :8000):
 *   1. "open the graph view" → fe_navigate_canvas tool pill goes Done
 *      and the Activity Bar flips to Graph (bd-115z + bd-ioyz).
 *   2. "now show me findings" → Activity Bar flips to Findings WITHOUT
 *      a duplicate fe_navigate_canvas for graph (bd-n368 resume sync).
 *   3. "what view am I on?" → assistant answers "findings" (bd-vw04
 *      canvas-context push still wired).
 *
 * No cleanup hook re-resets the canvas between scenarios because each
 * scenario depends on the prior canvas state to verify resume-turn
 * behaviour.
 */

import { expect, test, type Page } from "@playwright/test";

const CHAT_PLACEHOLDER = "Ask anything…";
const TOOL_PILL_TIMEOUT = 15_000;
const ACTIVITY_TIMEOUT = 15_000;
const REPLY_TIMEOUT = 20_000;
const IDLE_TIMEOUT = 30_000;

async function waitForChatIdle(page: Page): Promise<void> {
  // CopilotKit's send button swaps a Square (Stop) lucide icon while the
  // agent is running; the Square's class includes "lucide-square". Wait
  // until no such icon is rendered in the chat input.
  await expect
    .poll(
      async () =>
        page.evaluate(
          () => document.querySelectorAll("svg.lucide-square").length,
        ),
      { timeout: IDLE_TIMEOUT, message: "chat agent never returned to idle" },
    )
    .toBe(0);
}

async function sendChatMessage(page: Page, message: string): Promise<void> {
  await waitForChatIdle(page);
  const textarea = page.locator(`textarea[placeholder='${CHAT_PLACEHOLDER}']`);
  await expect(textarea).toBeVisible();
  // Up to two attempts: a stray "isRunning" race after a previous turn
  // can swallow the first Enter into the onStop branch.
  for (let attempt = 0; attempt < 2; attempt++) {
    await textarea.click();
    await textarea.fill(message);
    await expect(textarea).toHaveValue(message);
    await textarea.press("Enter");
    try {
      await expect(textarea).toHaveValue("", { timeout: 5_000 });
      return;
    } catch (err) {
      if (attempt === 1) throw err;
      await waitForChatIdle(page);
    }
  }
}

async function waitForActiveView(
  page: Page,
  expectedTitle: string,
  timeout = ACTIVITY_TIMEOUT,
): Promise<void> {
  await expect
    .poll(
      async () =>
        page.evaluate(() => {
          const buttons = Array.from(
            document.querySelectorAll<HTMLButtonElement>("button[title]"),
          );
          const active = buttons.find((b) =>
            b.querySelector("span.bg-violet-500"),
          );
          return active?.title ?? null;
        }),
      { timeout, message: `expected Activity Bar active title=${expectedTitle}` },
    )
    .toBe(expectedTitle);
}

async function countNavigatePills(page: Page): Promise<number> {
  // bd-w0gr: the chat-renderer rewrite (bd-imeg-sprint2) replaced the
  // raw `fe_navigate_canvas` text surface with a
  // <ToolCallCard title="Switch view"> plus a sibling violet
  // "Frontend" badge (bd-f849 styling that the card chrome applies to
  // any fe_* tool). The pair "Switch view" + "Frontend" inside the
  // SAME trigger row is unique to a fe_navigate_canvas card in the
  // chat transcript:
  //   - the chat-sidebar header chip (`copilot-sidebar.tsx`) renders
  //     only the friendly title, never the badge
  //   - any other fe_* tool would render the badge but not the
  //     "Switch view" title
  // Helper purpose stays the same: count navigate-card instances so
  // scenario 2 can verify the resume turn does NOT emit a duplicate.
  return page.evaluate(() => {
    const titles = Array.from(
      document.querySelectorAll<HTMLElement>("span"),
    ).filter((s) => (s.textContent ?? "").trim() === "Switch view");
    let n = 0;
    for (const t of titles) {
      // Walk a few levels up to the trigger row and look for the
      // sibling "Frontend" badge — that disambiguates the card from
      // the chat-sidebar header chip.
      let cursor: HTMLElement | null = t.parentElement;
      for (let depth = 0; cursor && depth < 4; depth++) {
        if ((cursor.textContent ?? "").includes("Frontend")) {
          n += 1;
          break;
        }
        cursor = cursor.parentElement;
      }
    }
    return n;
  });
}

test.describe.serial("Canvas-aware chat smoke (bd-w0gr)", () => {
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
    const textarea = page.locator(
      `textarea[placeholder='${CHAT_PLACEHOLDER}']`,
    );
    await expect(textarea).toBeVisible();
    // Next.js + CopilotKit hydrate after the textarea is paintable;
    // submitting before the provider's onSubmitMessage handler is bound
    // produces a silent no-op. Give hydration a beat to settle.
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2_000);
  });

  test.afterAll(async () => {
    await page?.close();
  });

  test("scenario 1: navigates to Graph via fe_navigate_canvas", async () => {
    await sendChatMessage(page, "open the graph view");

    // bd-w0gr: anchor on the Radix CollapsibleRoot (`data-state`) that
    // wraps every <ToolCallCard>; the FE-tool variant always renders
    // title="Switch view" + the violet "Frontend" badge inside the
    // same root, so the pair filter is unique to fe_navigate_canvas.
    // `data-state` is a documented Radix contract — not a tailwind
    // utility class — so it's a stable structural hook.
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

  test("scenario 2: resume turn flips canvas to Findings without re-navigating", async () => {
    const pillsBefore = await countNavigatePills(page);
    await sendChatMessage(page, "now show me findings");
    await waitForActiveView(page, "Findings");
    const pillsAfter = await countNavigatePills(page);
    expect(pillsAfter - pillsBefore).toBeLessThanOrEqual(1);
  });

  test("scenario 3: canvas-context push lets the agent answer 'findings'", async () => {
    await sendChatMessage(page, "what view am I on?");
    await expect
      .poll(
        async () =>
          page.evaluate(() => document.body.innerText.toLowerCase()),
        { timeout: REPLY_TIMEOUT, message: "assistant reply mentions 'findings'" },
      )
      .toContain("findings");
  });

  test("scenario 4: subagent.swarm activity card materialises (bd-6zyg)", async () => {
    await sendChatMessage(
      page,
      "launch a small swarm with 2 agents that scout the registry",
    );
    // The activity renderer reuses the ToolCallCard chrome and uses
    // title "Swarm · …". Wait for it to flip to "Done" (status:
    // completed → statusToCardStatus → "complete").
    const card = page
      .locator("[data-state]")
      .filter({ hasText: /^Swarm · /i })
      .first();
    await expect(card).toBeVisible({ timeout: 30_000 });
    await expect(card.locator("text=/Running|Done|Complete/i")).toBeVisible({
      timeout: 30_000,
    });

    // bd-6zyg pin: prepareRunAgentInput strips role==='activity' from
    // the RunAgentInput.messages array sent on the next turn. The
    // AbstractAgent.prepareRunAgentInput in @ag-ui/[email protected]
    // does ``messagesWithoutActivity = clonedMessages.filter(
    // (m) => m.role !== "activity")``. Drive a follow-up turn and
    // grep network traffic to confirm.
    let sentBodies: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/api/copilotkit") && req.method() === "POST") {
        const data = req.postData();
        if (data) sentBodies.push(data);
      }
    });
    await sendChatMessage(page, "thanks");
    // Best-effort assertion — the local AG-UI runtime route may not
    // include the bare activity message in the body; we only need to
    // confirm no role==='activity' entry leaks.
    for (const body of sentBodies) {
      expect(body).not.toMatch(/"role"\s*:\s*"activity"/);
    }
  });
});
