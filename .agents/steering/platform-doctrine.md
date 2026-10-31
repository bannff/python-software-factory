# Platform Doctrine — The Expert-Augmentation Engine

This file records product direction and current implementation context. The single normative control-plane authority is [`.agents/steering/factory-protocol.md`](../../.agents/steering/factory-protocol.md); when guidance conflicts, that file wins. `dev-principles.md` governs implementation practice.

## What this platform is

A **domain-agnostic expert-augmentation engine**: a constant set of mechanics (graph + recursive learning loop + games + blockchain/oracle + polyglot storage, all behind MCP), wrapped by a single interaction surface, specialized per business purely by **data**. The agent drives; a human steers. Security is the first domain — it is a *data pack*, not the engine.

The same engine modernizes any business: taxes, wineries, law, medicine, security. The expertise is contained in an agent (skills / SOP / steering); the bones are data-driven.

## The cockpit

the control-plane runtime Web (Next.js) is the one interaction surface: dashboards, graph, chat, metrics, timeline, and — when a task warrants it — embedded code editing with gutter decorations and the artifact-bound graph. The agent drives; the human watches, directs, and reaches in as deep as the task requires.

**One surface, no capability gating.** The Web client calls the *same* MCP pipes and can *invoke* anything. Depth is a **mode** of this cockpit (embedded Monaco + the existing agent + the `sandbox` brick), added when a task needs it — not a separate application. There is one cockpit until a second surface genuinely earns its place; "capability-shared, interaction-differentiated" is deferred, not foundational.

## Engine vs. domain pack

Everything sorts into "built once" (the engine) or "per-domain data" (the pack). This is the test of whether the bones are truly data-driven.

**Engine (built once, never per-domain):** the graph substrate, the recursive-loop machinery, the games/scoring engine, the LoRA/distillation path, the blockchain/oracle, the polyglot storage bricks, the MCP/A2A transport, the polymorphic brick pattern, and — on the client side — the presentation render surfaces (decorations, terminal mirror, navigable graph, panels).

**Domain pack (pure data/config):** the agent persona (skills + SOP + system prompt + tool allowlist), the taxonomy, the game config + ground truth, the presentation manifest (labels, finding-type descriptors, artifact-renderer hints, theme), and — eventually — a distilled LoRA adapter for that domain.

Only mechanic #1 (agents as experts) is *primarily* a pack concern; mechanics #2–#9 below are mostly engine. The expertise is the data; the mechanics are the engine.

### Discipline rules

1. **Zero `if domain == ...` in the engine or the client** — and equally, **no branch on the manifest id** (`if manifest == ...` is the same sin by another name). The domain manifest drives presentation; the persona/skills drive behavior. The enforcement mechanism is the backend's proven convention: trinary polymorphic params (`None` / `[]` / value) + registry-overlay (built-ins-win merge), never a domain switch. The persona→manifest pointer stays a *soft* reference with a generic fallback, never a hard 1:1 that recreates `domain_class` by the back door. If security cannot be expressed purely as a manifest + persona + bricks, the abstraction has a hole — find it early.
2. **Build security AS a domain pack, never as the engine.** Dogfood the abstraction the same way the backend already did (`defaults_code_scan_*` + security skills + CWE taxonomy are a data pack today). A deliberately different pack #2 (e.g. contract-clause review) is the cheap forcing function that proves the engine absorbed no domain-specific assumptions.

### Expertise layer vs. presentation layer

The agent IS the domain expert — `skills + SOP + system_prompt + agent_id` is the entire expertise contract (per bd:`python-factory-ziwqs`; no separate `domain_class` knob needed for behavior/recall). Presentation (what a finding looks like, taxonomy colors, artifact editors, vocabulary, theme) is a *separate, mostly-defaulted* manifest — overloading the persona with UI concerns breaks SRP. A persona declares which presentation manifest it uses, or falls back to a generic one. **Generic-by-default, enriched-by-data:** a brand-new domain lights up with neutral labels, a generic graph, and text artifacts at zero client cost, and is progressively enriched with data (and, only when warranted, a bespoke artifact editor).

## The nine best-practice mechanics

These are the modernization primitives. They are captured here with engineering-correct framing — a few are stated as "X beats Y" in casual conversation, but the defensible (and more powerful) version is composition, not rivalry.

1. **Agents as domain experts.** Strands `AgentSkills` (knowledge) + SOP (procedure) + system prompt + tool allowlist are registry data. An SOP constrains a procedure without freezing every team or topology: the Agent runtime may compose the smallest bounded objective-specific Graph or Swarm from registered personas, skills, tools, budgets, and structured-output contracts. Promote a topology into the small registered template catalog only after repeated evidence shows that it is stable and reusable. Skills are recall; SOPs bound orchestration.

2. **Graph as the relationship/reasoning layer.** Graph wins for relationship-heavy, traversal, reasoning workloads — it is the connective tissue, *not* a blanket replacement for a database. It is one role in a polyglot store (see #8), holding entities + relationships + reasoning/evidence chains.

3. **Recursive learning as a two-timescale system.** The online loop (memory recall + reward-shaped behavior, no weight change) and offline distillation (SFT/LoRA, weights change) are *not rivals* — they compose across two timescales: a **fast online timescale** (the loop) and a **slow offline timescale** (distillation). Crucially, **the loop is the data engine that produces the fine-tuning set**: Games contributes reward signals and evidence; Evals independently applies frozen policy and owns acceptance and promotion of evidence-bound trajectories. Flywheel: loop runs online → accumulates accepted trajectories in a landing zone → periodic distillation → better model → runs the loop better.

4. **Game theory as a reward/evidence layer.** Games scores strategic outcomes and emits reward signals and supporting evidence (for example TP/FP/novel); it does not decide whether an artifact, trajectory, or model is accepted or promoted. Evals owns those decisions under policy frozen before execution. Games also models adversarial/strategic dynamics (attacker vs defender, negotiation, markets), producing useful evidence for the recursive loop without becoming a second evaluation authority. Already domain-parameterized server-side via `domain_class` / `game_type` + `defaults_<domain>.py` (writer-side only — there's no agent in scope at `_store_learnings`; the approved `domain_class`→`recall_namespace` rename is pending, so sync this line when it lands).

5. **Light M/L (LoRA) for local agents.** When the model is local (Bedrock unreachable), the distilled adapter *is* how expertise ships — a domain pack eventually carries its own LoRA adapter, making it self-improving and portable. Hard prerequisite: a **trajectory landing-zone format** the loop writes and the distiller reads. This is currently unbuilt (the steering's own scope notes admit zero training jobs) — it is the keystone gap between vision and reality.

6. **Blockchain by property, not by slogan.** Justify per-property, which is unimpeachable: immutable **provenance** (an auditable chain of custody — a compliance *requirement* in law/tax/medicine, not a nice-to-have), a programmable **incentive economy** (the local currency *is* the RL reward layer — agents earn for verified outcomes, humans for novel catches), and **distributed trust** for multi-party domains. Storage rule: **anchor hashes, never store bulk data on-chain** (content-addressed blob + on-chain hash anchor).

7. **Agentic access via MCP/A2A; the MCP server is the capability gateway and oracle surface.** MCP exposes brick tools; A2A and native Strands Graph/Swarm provide in-process agent collaboration owned by the Agent brick. the control-plane runtime composes those Agent surfaces and the aggregator's capabilities without becoming another runtime. Making the MCP gateway surface the blockchain oracle gives a *single control plane* for both capability (tools) and trust (chain reads/writes). **Security consequence:** MCP then becomes the highest-trust component; a compromised MCP server = a compromised ledger. It MUST be authenticated and its chain-write authority tightly scoped before multi-user/cloud. **Placement guardrail:** the aggregator *surfaces the blockchain brick's oracle tools* — the ledger/oracle logic stays in the brick's `runtime/`, never embedded in the `mcp_server` base (tenet #6, no bespoke logic in bases). This is exactly why freeze-contract #3 is the *brick's* interface.

8. **Polyglot storage, four roles, unified by MCP.** Blob (large immutable artifacts — documents, code, reports, model weights), graph (relationships, optionally embedded via `neo4j_embedding`), KB (semantic/vector recall of facts), chain (integrity anchors/provenance over the other three). Separate by *role*, unified by *interface*, polymorphic adapters throughout. `graph-as-KB` is viable only for entity-attached facts; broad semantic recall still wants a dedicated vector KB. `blockchain-as-storage` means anchors only. (The distilled LoRA adapter from #5 is itself a blob artifact anchored by a chain hash — closing #4↔#5↔#6.)

9. **Engineering excellence — polymorphic tools, taxonomies as data.** Every brick is ports + adapters (networkx↔neo4j, chromadb↔neo4j_embedding, mock_ledger↔real chain, ollama↔bedrock). Per-domain taxonomies are data (graph brick's taxonomy registry + `graph://schemas/taxonomy/{domain}`). Polymorphism is what lets a domain swap its backend without touching logic — the tenet that holds #1–#8 together.

## The three-layer tool model

"Tools" means three different things; conflating them produces the wrong marketplace. Keep them separate.

1. **Expertise layer → agents (data).** Skills / SOP / prompt / tool allowlist in the registry. Not code, not an extension.
2. **Capability & connector layer → MCP tools/servers (server-side).** Brick tools *and* composed external MCP servers (Outlook, Jira, Salesforce, GitHub, …). The Web cockpit auto-surfaces these tools via the CopilotKit/AG-UI dispatcher — adding a connector is zero client code. **This** is the connector marketplace: the MCP ecosystem, composed server-side.
3. **Visualization layer → render surfaces (compile-time).** The graph view, panels, artifact editors — the engine's render surfaces. Delivered through the shared renderer + a generic fallback, which covers most domains; a bespoke surface earns its place only when the data cannot be rendered generically.

**Mental-model correction.** In VS Code, a "tool" is an extension *the user* installs to get *commands*. In agent-first, the **agent** consumes tools via MCP; the client only *visualizes*. Do not build a per-tool extension marketplace — that is the wrong axis. The two marketplaces that matter: **MCP connectors** (capabilities) and **domain packs** (persona + skills + SOP + taxonomy + manifest + adapter).

## Open decisions (working defaults — revisit, don't treat as frozen)

- **Persona-first vs. engagement-first.** Working default: **engagement-first** — open a domain engagement (e.g. a "tax engagement" or a target repo), which pins the domain/manifest, with a default persona attached; any persona can then operate within it. Rationale: multiple personas may work the same artifact. Reversible.
- **Three contracts to freeze before parallel build.** (1) the presentation-manifest schema (fetched like `unified_personas()`) — this *depends on first resolving the engagement-vs-persona binding model* above, since that decides how the manifest is bound/fetched; freeze the two together or the schema churns the moment engagement-first lands; (2) the trajectory landing-zone format (closes #3↔#5); (3) the oracle interface (the blockchain brick's interface for writing provenance / reading currency, with trust scope). Getting these right up front is what lets independent tracks build in parallel without drifting — the way to "start and actually finish."

## Cross-references

- North Star: `.agents/steering/factory-protocol.md`
- How we write code: `.agents/steering/dev-principles.md`
- Domain-agnostic backend substrate (already shipped): `.agents/recipes/domain-agnostic-substrate.md`, epics bd:`python-factory-hadbi` + bd:`python-factory-d4roe`
- Rendering protocol: `.agents/steering/a2ui-protocol.md`
- Graph taxonomy registry: `.agents/steering/graph-taxonomy.md`
- Provenance, Telemetry OTLP ingestion, and subject-focused Metrics: `.kiro/specs/the control-plane runtime-graph-provenance/`
