# GPT-5.x on Bedrock Mantle (OpenAI Responses API)

How the control-plane runtime runs OpenAI **GPT-5.5 / GPT-5.4** as Strands agents on Amazon
Bedrock, and the gotchas that come with the Responses-API path. Added in
bd:python-factory-e2610. strands-expert verdicts `3057b5fd` + `56ff6d6d`.

## TL;DR

- Any persona whose `model` starts with `openai.gpt-5` resolves to an
  `OpenAIResponsesModel` routed through Bedrock's **mantle** endpoint — see
  `components/agent/src/factory/agent/runtime/adapters/strands_mantle_model.py`.
- `openai.gpt-oss-*` is open-weight and Converse-served — it stays on the
  bare-string path and is NOT a mantle model.
- The built-in `developer` persona (`registry/defaults_developer.py`) runs on
  `openai.gpt-5.5`. Drive it via `spawn_subagent("developer", task)` or
  `spawn_swarm(["developer", ...], task)` / `spawn_graph`.

## Regions (model-gated, independent of `AWS_DEFAULT_REGION`)

- `openai.gpt-5.5` → `us-east-2` (Ohio) **only**.
- `openai.gpt-5.4` → `us-east-2` or `us-west-2` (Oregon); also GovCloud US-West.
- Set `BEDROCK_MANTLE_REGION` (default `us-east-2`). This is the mantle call's
  region only — it does not change the rest of the stack's region.

## Credentials

- No API key. A fresh Bedrock bearer token is minted **per request** from the
  standard AWS credential chain via `aws-bedrock-token-generator`.
- Needs valid AWS creds for the account/region with GPT model access enabled.
  Stale creds surface as `401 ... security token ... expired` — refresh (refresh your credentials) and retry.

## Endpoint path gotcha (native in Strands 1.50.2)

The GA models are served at **`/openai/v1`**. Strands 1.50.2 resolves that
path natively for `openai.gpt-5.*` when `OpenAIResponsesModel` receives
`bedrock_mantle_config={"region": region}`; it also mints a fresh bearer token
for every request. The factory therefore uses the native model directly and
does not reconstruct client arguments or call the token generator itself.

`BEDROCK_MANTLE_BASE_URL` remains a narrow custom-endpoint escape hatch. Its
subclass delegates to `super()._resolve_client_args()` and replaces only
`base_url`, preserving native region and token-refresh behavior. A canary pins
`_resolve_mantle_base_path("openai.gpt-5.5") == "/openai/v1"` and the public
constructor surface.

## Model behavior gotchas

- Tool calling is fully supported on the Responses path — the old "prefer
  Anthropic for tools" advice is stale. Stream events are the same canonical
  shapes (`toolUse`/`toolResult`/`contentBlock` deltas), so the AG-UI bridge and
  `translate_strands_event` work unchanged.
- Tool-call arguments arrive as one complete JSON blob at the END of the stream
  (not incrementally like Bedrock Converse).
- Use `max_output_tokens`, not `max_tokens` (reasoning tokens count against it).
- `reasoningContent` is stripped from multi-turn outgoing messages — reasoning
  is not replayed across tool calls. Fine for normal use.
- `temperature` is often rejected by GPT-5 reasoning models — leave it unset and
  steer with `reasoning.effort` instead (default `medium`, per AWS;
  `BEDROCK_MANTLE_REASONING_EFFORT`).
- Do NOT set `stateful=True` on a swarm node — it forces a NullConversationManager
  and fights Strands' reconstructed shared-context model. The spawn path doesn't.
- `parallel_tool_calls=false` is a valid Responses param, but mantle's honoring
  is unverified — we rely on the transport-agnostic `ParallelToolDedupPlugin`.

## Letting a dev agent see local code

The `developer` persona has no `tools` allowlist, so `_build_specialist` gives it
the full chat MCP toolset plus `shell` + `python_repl`. It reads/edits the repo
by running shell/python (e.g. `ls`, `cat`, `grep`, `git`) in the API process's
working directory — i.e. wherever the control-plane runtime was started. Every shell/python
execution is gated by `ShellApprovalPlugin` (the Approve/Deny card in chat), so
the agent cannot touch the repo without an explicit approval per command. If you
want frictionless read-only browsing, consider adding `file_read` to the agent's
toolset (it's a read-only `strands_tools` tool) — currently not in the shared
chat toolset.

## Install

`strands-agents[openai]==1.50.2` is a core runtime dependency and brings
`openai>=2.0.0` plus `aws-bedrock-token-generator`. It is exact-pinned in the
workspace, Agent brick, and the control-plane runtime manifests; no separate OpenAI optional
extra or standalone token-generator declaration is needed.
