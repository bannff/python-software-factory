# VS Code Copilot Customizations

This repository now includes a minimal workspace-scoped Copilot customization setup in `.github/`.

## What Was Added

### Custom Agents
- `.github/agents/factory-lead.agent.md`
- `.github/agents/implementer.agent.md`
- `.github/agents/meta-architect.agent.md`
- `.github/agents/qa-tester.agent.md`
- `.github/agents/doc-writer.agent.md`
- `.github/agents/strands-expert.agent.md`

These appear in the VS Code agent picker and can also be used as sub-agents when Copilot supports custom agent delegation.
`Factory Lead` is the easiest starting point because it mirrors the specialist-dispatch workflow from Kiro.

### Hooks
- `.github/hooks/pretool-guardrails.json`
- `.github/hooks/stop-reminders.json`

These call small scripts in `scripts/hooks/`:
- `pretool_guardrails.py` asks for confirmation on obviously destructive commands and warns on new branch creation.
- `stop_reminders.py` emits a short reminder at session end when the worktree is still dirty.

## How To Use It

1. Open Copilot Chat in VS Code.
2. Use the agent picker to select one of the custom agents.
3. Work normally; supported Copilot hook events will pick up the workspace hook JSON files automatically.

## Recommended Usage

- Use `Factory Lead` when you want the agent to decide the workflow for you.
- Use `Factory Meta-Architect` before larger design changes.
- Use `Factory Implementer` for code changes.
- Use `Factory QA Tester` after implementation or for bug reproduction.
- Use `Factory Doc Writer` when interfaces, workflows, or docs changed.

## Notes

- This is a conservative scaffold, not a full Kiro hook port.
- Deterministic enforcement belongs in hooks.
- Guidance, delegation, and role behavior belong in custom agents and workspace instructions.
- If you want stricter enforcement later, extend the Python scripts rather than adding large JSON hook payloads.