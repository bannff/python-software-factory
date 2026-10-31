# GitHub Operations Skills

This file is the portable operating manual for the GitHub Operations agent.

## How to use
- Start with the narrowest GitHub artifact that matches the request.
- Prefer repo-local templates for durable structure.
- Prefer org-level Projects when work spans multiple repositories.
- Keep each artifact small enough to be actionable in one pass.

## Issue Skill
- Use for bugs, features, chores, and scoped work requests.
- Template: `.github/agents/github-operations/templates/issue.md`
- Required fields: problem, goal, scope, acceptance criteria.
- Output: one issue draft with a clear title, body, and suggested labels.

## Discussion Skill
- Use for RFCs, open questions, design tradeoffs, and decisions.
- Template: `.github/agents/github-operations/templates/discussion.md`
- Required fields: topic, context, options, proposed direction.
- Output: one discussion draft that makes the decision surface explicit.

## Project Skill
- Use for multi-item execution plans, milestones, and team coordination.
- Template: `.github/agents/github-operations/templates/project.md`
- Required fields: objective, scope, views, intake rule, success criteria.
- Output: a project board proposal plus starter item structure.

## Pull Request Skill
- Use when work is ready to merge or needs review packaging.
- Template: `.github/agents/github-operations/templates/pull_request.md`
- Required fields: description, related issue, changes made, validation.
- Output: a PR draft that is merge-ready and reviewer-friendly.

## Label Skill
- Use to define or normalize team taxonomy.
- Template: `.github/agents/github-operations/templates/label.md`
- Required fields: label name, purpose, color, lifecycle meaning.
- Output: a label set proposal that is consistent and minimal.

## Repository Skill
- Use for repo bootstrap, governance, or consistency checks.
- Template: `.github/agents/github-operations/templates/repository.md`
- Required fields: purpose, ownership, conventions, required surfaces.
- Output: a repo operating profile or bootstrap checklist.

## Release Skill
- Use for versioned delivery notes, changelogs, and rollout summaries.
- Template: `.github/agents/github-operations/templates/release.md`
- Required fields: summary, impact, migration notes, links.
- Output: a concise release note with clear user impact.

## Wiki Skill
- Use for durable how-to documentation that is not a decision record.
- Template: `.github/agents/github-operations/templates/wiki.md`
- Required fields: topic, canonical source, steps, links.
- Output: a wiki page draft that links back to source-of-truth docs.

## Workflow Skill
- Use for GitHub Actions, automations, or event-driven process changes.
- Template: `.github/agents/github-operations/templates/workflow.md`
- Required fields: trigger, job, permissions, secrets, outputs.
- Output: a workflow draft with minimal permissions and clear outcomes.

## Default behavior
- If the request is ambiguous, ask for the target artifact and the intended audience.
- If the request spans multiple artifacts, draft them separately.
- If the request is high risk or externally visible, stop and escalate the review depth.