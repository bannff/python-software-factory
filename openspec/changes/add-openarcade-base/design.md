## Context

OpenArcade is a sibling Polylith project inside the python-factory
monorepo. Control-plane bricks live under `components/` and the Flet
UI shell lives under `projects/openarcade/wall/`. Every other
sub-project in this monorepo already has a corresponding
`bases/<name>/` Polylith base (see `bases/{api,blueprint,dashboard,flet_dashboard,mcp_server,pipeline_dataset,worker}`)
that wires its consumed bricks into a single installable unit with a
typed entry point and (where applicable) a Typer CLI. OpenArcade does
not — `pyproject.toml` and `BRICK.yaml` exist under
`projects/openarcade/` but are app-level, not base-level, and
deployers cannot `pip install` an "openarcade" deliverable. See
`proposal.md - Why` for motivation.

The base must be lean: it cannot pull `fastmcp` (per the existing
"lean-env note" in `projects/openarcade/README.md`). It must use
`factory.<brick>.runtime.*` import paths and never
`factory.<brick>.interface`.

## Goals / Non-Goals

**Goals:**

- A `bases/openarcade/` directory that other Polylith tooling
  (`poly info`, `foreman info`, `foreman resolve-deps`) recognizes
  as a first-class base.
- A stable Python entry point at `factory.openarcade` so downstream
  consumers can `import factory.openarcade` without knowing about the
  wall module path.
- A Typer CLI for headless ops (CI smoke, scripted launches, ROM
  scans) without forcing a desktop window.
- Explicit, auditable composition: every brick the base uses is
  listed in `BRICK.yaml`.
- Backward compatibility: `projects/openarcade/run.sh` and
  `run_web.sh` keep working without any operator-side change.

**Non-Goals:**

- We do NOT move the wall app code into the base. The wall stays
  under `projects/openarcade/wall/`; the base composes it by
  import. Moving wall code would balloon the base and entangle
  app-level concerns (fixtures, themes) with base-level wiring.
- We do NOT introduce a new control-plane brick. This change
  consumes the existing five and the existing `ui` brick.
- We do NOT add new third-party dependencies. The lean set
  (`flet`, `pydantic`, `structlog`, `typer`, `pyyaml`) is
  already declared.
- We do NOT address the parked real-hardware NCI handoff or the
  Brook Neo-Arcade udev validation. Those remain the human's
  hardware-loop concerns.

## Decisions

### Decision: Use `factory.<brick>.interface` for every brick EXCEPT `factory.ui`
**Why:** Verified by `grep -r 'fastmcp' components/`: only
`components/ui/src/factory/ui/interface.py` imports `fastmcp`. The
other bricks' `interface.py` files (curator, launch, library,
arcade_config, state) are thin Polylith facade modules that
re-export from `runtime.*` without pulling any heavyweight deps.
The wall already imports from `factory.curator.interface` (in
`curator_bridge.py`), `factory.launch.interface` (in
`launch_handler.py`), and `factory.arcade_config.interface` (in
`retroarch_config.py`) — these are the established public API
paths and the base should follow them. The one exception is
`factory.ui`: its `interface` module is the MCP surface, so the
base must import the Flet adapter directly via
`factory.ui.runtime.adapters.flet_adapter` (per the existing
lean-env note in `projects/openarcade/README.md`).
**Alternatives considered:**
- Use `runtime.*` paths uniformly across all bricks — rejected:
  would force a refactor of every existing wall import for no
  runtime benefit (none of them pull `fastmcp`); also breaks
  Polylith convention of treating `interface` as the public API.
- Add `fastmcp` to the lean set — rejected: `fastmcp` is 30+ MB of
  transitive deps for a kiosk that never speaks MCP at runtime.
- Re-package wall imports under a new facade — rejected: the wall
  already imports correctly via `interface.*`; just replicate
  that pattern in the base.

### Decision: Keep the wall app code in `projects/openarcade/wall/`; compose by import
**Why:** The wall is 16 files of Flet UI builders and a navigator
shell that are pure-function-tested and would be a maintenance
burden to relocate. The base's job is wiring, not hosting.
**Alternatives considered:**
- Move the wall into the base — rejected: mixes app and base
  concerns; bloats the base; the `ARCHITECTURE.md` "dependency
  direction" diagram (`domain → wall → app.py`) would no longer
  hold.
- Symlink the wall from inside the base — rejected: Polylith's
  `foreman` walks the real tree; symlinks cause path-resolution
  surprises in `pip install -e` and CI.

### Decision: Project-local `declared-bricks` list in `BRICK.yaml` + custom AST guard
**Why:** The `bricks_consumed` field is not a Polylith-standard
field — no existing `BRICK.yaml` in this repo uses it. We
introduce a project-local `declared-bricks` list as the
human-readable intent declaration (it shows up in `poly info`),
and pair it with a custom AST guard (task 5.3) that walks the
base's source, collects every `factory.<x>` import, and fails the
build when `<x>` is not in `declared-bricks`. The two together
give a single source of truth (the YAML) with machine-enforced
drift detection (the AST guard). `foreman resolve-deps` is
independent of this: it resolves imports via AST too, but
operates on the entire workspace, not the base's `declared-bricks`
list.
**Alternatives considered:**
- Use a Polylith-standard field — rejected: no such field exists;
  introducing a new standard is out of scope for this change.
- Implicit composition (only `foreman resolve-deps`) — rejected:
  no `BRICK.yaml` declaration means the dependency graph is not
  human-auditable from the brick file alone.
- Forbid new brick imports without a separate change — rejected:
  the AST guard is lighter-weight and catches drift at PR time.

### Decision: Typer CLI colocated in the base, not the wall
**Why:** The CLI is part of the base's headless contract. Putting it
under `projects/openarcade/wall/` would force a re-import of the
wall just to run a scan from CI.
**Alternatives considered:**
- Reuse `projects/openarcade/tools/` if it has a CLI — it does not
  (the `tools/` dir is the human's working scratch).
- Expose the CLI as a separate project — rejected: not enough
  surface area to justify a second distribution.

## Risks / Trade-offs

- **[Risk] Undeclared-brick drift** — a maintainer adds `import
  factory.new_brick` to the base without updating `BRICK.yaml`'s
  `declared-bricks` list.
  **Mitigation:** the custom AST guard from task 5.3 (run in
  `pytest` and CI) fails the build with the undeclared brick's
  name when a source import is not in `declared-bricks`.
- **[Risk] `opencode-plugin-openspec` agent activation side-effects**
  — the `openspec-plan` agent may try to write into the base
  directory because `openspec/config.yaml` now exists. **Mitigation:**
  scope the agent's `edit` permissions to `openspec/**` and
  `projects/openarcade/docs/**` only (default from the plugin's
  policy); do not run `/opsx:propose` from inside `bases/openarcade/`.
- **[Risk] Wall fixtures leak into the base** — `wall/fixtures.py`
  builds a synthetic ROM tree. If a future change calls it from the
  base's CLI scan path, production scans will see fixture data.
  **Mitigation:** the `openarcade scan` CLI must explicitly opt out
  of the fixtures path (env var `OPENARCADE_NO_FIXTURES=1`).
- **[Risk] Conflict with `feat/openarcade-build` uncommitted
  branch** — the worktree currently has uncommitted wall work on
  `feat/openarcade-build`. The base change touches the same
  `projects/openarcade/main.py` and shell scripts. **Mitigation:**
  this change is authored on `main` (or a fresh branch) and the
  human rebases `feat/openarcade-build` after review.
- **[Trade-off] Two pyproject.toml files for one project** — the
  app-level `projects/openarcade/pyproject.toml` and the new
  base-level `bases/openarcade/pyproject.toml` will both exist.
  Acceptable because they declare different concerns (app
  dev-deps vs. base runtime/distribution); explicit beats implicit.

## Migration Plan

1. **Land the base on a fresh branch** (e.g. `feat/openarcade-base`)
   off `main` with the `bases/openarcade/` skeleton + tests.
2. **Convert shell scripts to wrappers.** Update
   `projects/openarcade/run.sh` and `run_web.sh` to call
   `python -m factory.openarcade` after setting the existing env
   vars. Keep the old `PYTHONPATH` semantics for one release as a
   fallback path that the new entry point short-circuits.
3. **Re-target `projects/openarcade/main.py`.** Replace its
   wall-launch body with `from factory.openarcade import run_wall;
   run_wall()`. The file stays for backward compat with anyone
   running `python projects/openarcade/main.py` directly.
4. **Run CI.** `foreman check` + `pytest` for the new base plus
   the existing wall tests. The `feat/openarcade-build` branch
   must rebase on top and pass the same CI.
5. **Rollback.** Revert the merge commit. The shell scripts
   detect the absence of the `factory.openarcade` module and
   fall back to the pre-base `PYTHONPATH` invocation, so
   rollback is safe even if a partial state is deployed.
6. **Archive the change** via `/opsx:archive` after CI is green
   on `main` for one release cycle.

## Open Questions

- Should the base expose a `python -m factory.openarcade` console
  script in addition to the Typer CLI? (Resolves to yes if
  `foreman resolve-deps` already wires it; otherwise defer to a
  follow-up change.)
- Should `bricks_consumed` be enforced as a CI gate *now* or in a
  separate "lint pass" change? (Deferrable — both work, the
  enforce-now path is shorter.)
