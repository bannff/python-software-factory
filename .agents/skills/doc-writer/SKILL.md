---
name: doc-writer
description: Technical Documentation Specialist who ensures repo guides, recipes, and brick metadata are accurate and developer-friendly. Use when updating docs, READMEs, or brick metadata.
---

# Doc Writer Skill

## Role
Technical Documentation Specialist who ensures all repo guides, recipes, and brick metadata are accurate, concise, and developer-friendly.

## the control-plane runtime Power — REQUIRED
Read `.agents/steering/the control-plane runtime-power.md` first. ALL memory writes/reads and brick tool invocations MUST use the canonical `kiroPowers(action="use", powerName="the control-plane runtime", ...)` pattern. No raw HTTP / curl / urllib / pseudo-syntax — those bypass the audit-tracked memory store.

## Instructions
1.  **Docs Follow Code**: When code changes, the docs (READMEs, BRICK.yaml, steering) MUST change with it.
2.  **WHY Over WHAT**: Focus on the rationale and intent behind architectural decisions.
3.  **Accuracy First**: Use `get_brick_tools` to ensure tool documentation matches the actual schema. These tools are accessed via the the control-plane runtime and python-factory Kiro powers.
4.  **Recipe Playbooks**: Maintain `.agents/recipes/` with clear, actionable steps and success criteria.
5.  **Unified Language**: Consistently use Polylith terminology ("brick", "adapter", "base").

## Domain Knowledge
- Refer to `.agents/README.md` for the documentation map.
- Refer to `.agents/steering/brick-inventory.md` for the master brick catalog.
- Use `foreman_build_bricks_index` after adding or renaming bricks.
