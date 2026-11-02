---
description: Perform a formal architectural review of a proposed change or design.
---

1.  **Understand the Proposal**
    Identify the core problem being solved and the proposed architectural impact.

2.  **Map to Workspace**
    Which bricks are affected? Are new bricks or adapters required?

3.  **Run Compliance Check**
    // turbo
    Run `foreman_guardian_check` (via python-factory power) to establish the current workspace state.

4.  **Validate Against 10 Tenets**
    Verify the proposal against the 10 core repository tenets (MCP-first, <200 LOC, No cross-imports, etc.).

5.  **Check Memory**
    Query the `companion-x` memory brick for any prior architectural decisions related to this component.

6.  **Provide Verdict**
    Issue a verdict: APPROVE, APPROVE WITH NOTES, or BLOCK.

7.  **Log Decision**
    // turbo
    Store the review outcome in the `companion-x` memory brick for future reference.
