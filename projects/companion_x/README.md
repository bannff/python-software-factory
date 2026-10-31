# Project: the control-plane project

the control-plane runtime is the domain-neutral runtime control plane and Next.js cockpit; security is domain pack #1, not the engine. It dynamically assembles bounded objective teams through Agent brick surfaces and invokes capability bricks through MCP—it is not another agent runtime. See the normative ownership doctrine in [`.agents/steering/factory-protocol.md`](../../.agents/steering/factory-protocol.md).

## Brick Wiring

The authoritative project wiring is the `[tool.polylith.bricks]` table in
[`pyproject.toml`](pyproject.toml). Do not duplicate that mutable inventory in
this README; use `BRICKS_INDEX.yaml` for workspace discovery and the project
configuration for the exact deployable set.

## Local Dev (No Containers)

The fastest way to run the control-plane runtime locally — zero Docker, zero infrastructure.
All bricks use lightweight file-based or in-memory adapters.

### Adapter Stack

| Brick | Adapter | Env Var | Persistence |
|-------|---------|---------|-------------|
| KB | ChromaDB PersistentClient | `FACTORY_KB_ADAPTER=chromadb` | `./chroma_data/` (disk) |
| Memory | ChromaDB A-MEM | `FACTORY_MEMORY_ADAPTER=amem` | `./chroma_memory/` (disk) |
| Graph | persistent NetworkX | `FACTORY_GRAPH_ADAPTER=persistent_networkx` | Integrity-checked snapshot in local Storage blob store |
| Events | SQLite shared file | `EVENTS_BACKEND=sqlite` | Durable event history with configured retention |
| Telemetry | SQLite document store | `TELEMETRY_SQLITE_PATH=.storage/telemetry.db` | Dedicated raw window + daily rollups |
| Cache | memory | `FACTORY_CACHE_ADAPTER=memory` | Ephemeral |
| Worker | memory | `FACTORY_WORKER_BACKEND=memory` | Ephemeral |
| Storage | memory | `FACTORY_STORAGE_ADAPTER=memory` | Ephemeral |
| Blockchain | mock_ledger | `BLOCKCHAIN_ADAPTER=mock_ledger` | Ephemeral |
| Dataset | csv_can_ingest | `FACTORY_DATASET_ADAPTER=csv_can_ingest` | File-based (CSV/TXT) |

KB and Memory both use ChromaDB's built-in `all-MiniLM-L6-v2` sentence-transformers model for embeddings — no external embedding API needed.

### Run

The recommended launcher generates one ephemeral local MCP credential when the
`.env` leaves it blank, shares it only with the API and Next server processes,
and stops both on Ctrl-C. It also persists that token to a `0600` file at
`projects/the control-plane project/.storage/local-mcp-token` (removed when the launcher
stops), so a second process — a hand-started `npm run dev`, a smoke stack — can
join the running API without this shell's environment:

```bash
./scripts/the control-plane runtime-ui.sh
```

For manual two-terminal startup, generate one URL-safe token and export the
**same value** in both terminals before the commands below (the dashboard's
`MCP_LOCAL_AUTH_TOKEN` takes precedence over the launcher's token file):

```bash
export MCP_LOCAL_AUTH_TOKEN="<same-generated-token>"

# Terminal 1 — API
set -a
source projects/the control-plane project/.env
set +a
uv run python projects/the control-plane project/main.py

# Terminal 2 — Next.js frontend (same server-only local auth env)
set -a
source projects/the control-plane project/.env
set +a
cd frontends/next-dashboard && npm run dev
```

> The editable install of `python-factory` puts every brick's `src/` on the Python path automatically via Hatchling's `[tool.hatch.build] dev-mode-dirs` declaration in `pyproject.toml` — no `PYTHONPATH` overrides needed for `uv run`, `python -m`, Kiro powers, or the API process (bd:python-factory-9wcd).

- Dashboard: [http://localhost:3000](http://localhost:3000)
- API: [http://localhost:8000](http://localhost:8000)

The `.env` in `projects/the control-plane project/` now matches the lightweight local stack:

- `persistent_networkx` graph (integrity-checked snapshots in the local blob store) and telemetry isolated in its own `.storage/telemetry.db` with a Scheduler-owned daily retention job, so Timeline stays live and the general document store stays small
- `chromadb` KB and `amem` memory persisted locally on disk
- `openrouter` as the default chat provider (`COMPANION_X_CHAT_MODEL=openrouter`, `OPENROUTER_MODEL=<vendor>/<model>`); `ollama/<model>` and bare Bedrock ids remain selectable
- `FACTORY_API_PORT=8000`, matching the default local API port
- the control-plane runtime chat runs on the Strands Agents SDK over MCP v2 (route-flipped back from LangGraph in #89 — Strands regained MCP v2 support); the LangChain/LangGraph runtime is dormant, selectable via `AGENT_RUNTIME_ADAPTER=langchain` with deps in the `langgraph-legacy` group, and reaches MCP through the platform tool invoker with a curated tool set
- Chat conversations persist across API restarts via the strands `SessionManager` over the `SqlSessionRepository` (storage-brick `SQLStore` port; backend-swappable to Postgres/Aurora) keyed by `agent_id-thread_id`; storage defaults to `./.storage/strands-sessions.db`, and durable session metadata lives in the `session` brick at `./.storage/sessions.db`

Before starting the API, make sure Ollama is running and the local chat model is present:

```bash
ollama pull llama3.2
```

If you want to switch back to Bedrock, change these env vars and restart the API:

```bash
FACTORY_LLM_ADAPTER=bedrock
FACTORY_LLM_EMBEDDING_ADAPTER=bedrock
COMPANION_X_CHAT_MODEL=
```

## Run Modes

The container supports these run modes via `RUN_MODE`:

| Mode | Description |
|------|-------------|
| `api` | Unified MCP + REST + SSE + AG-UI server via uvicorn (default) |
| `mcp` | Standalone MCP aggregator server (stdio) |
| `worker` | SQS long-poll worker (Fargate) |

The Docker image defaults to `RUN_MODE=api`, which is what `docker-compose.yml` uses.

## Full Stack (Docker Compose)

For the full infrastructure stack (Neo4j, Redis, LocalStack) — needed for sandbox challenges, persistent graph, and AWS emulation.

Default `docker-compose.yml` starts these services:

| Service | Image | Ports | Purpose |
|---------|-------|-------|---------|
| neo4j | `neo4j:5-enterprise` | 17474, 17687 | Graph database |
| redis | `redis:7-alpine` | 16379 | Cache / pub-sub |
| localstack | `localstack/localstack:latest` | 4566 | AWS emulation (`ENFORCE_IAM=1`) |
| awscli | `amazon/aws-cli:latest` | — | Sidecar for CFN deploys into LocalStack |
| the control-plane project-api | (built) | 8001→8000 | Unified MCP+API, `SANDBOX_ADAPTER=localstack` |
| the control-plane project-next | (built) | 3001 | Next.js dashboard |
| the control-plane project-seed | `curlimages/curl` | — | One-shot seed job |

`SANDBOX_ADAPTER=localstack` is the default for both API and MCP containers. Security challenges (IDOR warehouse, IAM privesc, SSRF Lambda) run as Lambda functions inside LocalStack, deployed via CloudFormation templates in `challenges/`.

## Makefile Targets

```
make up                 — Start everything (neo4j + redis + localstack + app)
make stop               — Stop everything
make deploy-challenges  — Deploy CFN templates into LocalStack (iam-privesc, ssrf-lambda, idor-warehouse)
make dev                — Start infra only (neo4j + redis + localstack)
make logs               — Tail app logs
make test               — Run project tests
make build              — Build Docker images
```

## Config

See `pyproject.toml` for the full brick map and dependencies.

## Chronos-2 CAN Classification Probe

the control-plane runtime and the `machine_learning` brick use the same immutable native identity: public class `chronos.Chronos2Pipeline`, model `amazon/chronos-2`, revision `29ec3766d36d6f73f0696f85560a422f50e8498c`, with exact pins `chronos-forecasting==2.3.1` and `peft==0.19.1`.

Training/authoring is the only phase allowed to acquire that Hub revision. It persists the complete backbone with native `save_pretrained(..., safe_serialization=True)`. Frozen-backbone probe training is the default; optional LoRA uses only PEFT `save_pretrained`/`from_pretrained` with fixed `q`/`k`/`v`/`o` attention targets. The probe is strict Torch weights-only data; no custom raw adapter state dict is supported.

A `ModelPassport` is the sole cold/production authority. It binds the digest-complete native tree and exact class, model, revision, package, feature, probe, scaler, and adapter metadata. Promotion is revision 1 candidate → isolated fresh-process conformance → revision 2 promotable. Candidate, cold, and fresh inference first snapshot and verify exact local bytes, then use native `from_pretrained(local_path, local_files_only=True)`; they do not depend on the Hub, cache, network, process pipeline caches, or Chronos-local environment overrides.

Production calls `ml_predict_neural_passport` with the exact promoted Chronos passport reference and omits `live_timing_uri`/`live_timing_digest`. LNN/LTC timing requirements and LSTM/TCN/PatchTST/LightGBM behavior are unchanged. This is a pooled Chronos-2 CAN classification embedding probe, **not** a forecasting endpoint.

Targeted validation:

```bash
uv lock --check
uv run pytest components/machine_learning/test/factory/machine_learning/test_chronos_timeseries.py components/machine_learning/test/factory/machine_learning/test_chronos_passport_mcp.py components/machine_learning/test/factory/machine_learning/test_chronos_passport_strict.py components/machine_learning/test/factory/machine_learning/test_neural_passport_subprocess.py
git diff --check
```

## Durable Native CAN Lifecycle

`ml_train_can_portfolio` accepts a Dataset materialization request and supports
`lightgbm` (default), `lnn`, and `chronos`. It reconciles the Dataset terminal,
then trains from exact family refs: LightGBM uses `contract`/`x_2d`/`y`; LNN
uses `contract`/`x_3d`/`y`/`timespans` and derives its timing config from that
sealed ref; Chronos uses `contract`/`x_3d`/`y` and requires a caller-supplied
sealed local `model_config.local_backbone_ref`. LNN artifacts live under the
dedicated `ML_LNN_MODEL_ROOT`, which the acceptance config places beneath
`ML_MODEL_PASSPORT_ROOT`; Chronos validates its backbone and model trees beneath
the same passport authority. Native effects use deterministic job identities
and immutable replay records, allowing a retry to reconcile an interruption
after the record exists but before its effect receipt is stored.

The acceptance path issues revision-1 candidates with
`ml_issue_can_passports`, promotes each exact candidate through the generic
authoring-gated `ml_verify_and_promote_can_passport`, and cold-scores revision 2
with `ml_predict_neural_passport` after a real API restart. LNN additionally
binds request-scoped live timing by URI and digest; Chronos reloads its sealed
local backbone. Equal `attempt_id` retries replay the same terminal, while reuse
with changed semantic inputs returns `conflict`.

Run the real two-PID Streamable HTTP acceptance without external package or
model acquisition:

```bash
NO_PROXY=127.0.0.1,localhost \
HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 \
uv run --offline pytest \
  projects/the control-plane project/test/test_lnn_chronos_api_restart.py -q
```

The test uses localhost `/mcp/` by design, starts different API PIDs against the
same durable roots, confirms the restarted process has no warm model state, and
rejects tampered LNN model/timing, Chronos backbone, and passport bytes while
keeping the MCP server healthy.

## Native MLX Time-Series Models

MLX-native LSTM and TCN jobs run only on Darwin arm64 and bind the frozen lifecycle identity `mlx / 0.31.1 / mlx.nn.Module.load_weights / mlx-safetensors / local-mlx-isolated-v1`. the control-plane runtime uses the exact conditional direct pin `mlx==0.31.1; platform_system == "Darwin" and platform_machine == "arm64"`.

Native artifacts are immutable under `${ML_MODEL_PASSPORT_ROOT}/models/mlx/<digest>/` and contain exactly `model.safetensors` and canonical `factory_model.json`. Promotion is revision-1 candidate → isolated conformance → revision-2 promotable. Generic `ml_predict_timeseries` rejects durable MLX inference; production must call `ml_predict_neural_passport` with the exact promoted revision-2 passport reference.

## Darwin arm64 OpenMP Runtime Contract

On Darwin arm64, the supported ML environment command is:

```bash
uvx --from uv==0.12.0 uv sync --group ml --config-settings-package lightgbm:cmake.define.USE_OPENMP=OFF
```

This fail-closed command resolves exact `lightgbm==4.7.0` from its official PyPI sdist (SHA256 `f8e20f682c9aabd000bcf4a7ed8aa6f473c1adfecccae34ec24e823d156f4af0`) and builds it without OpenMP. The build setting is intentionally command-scoped: non-Darwin platforms continue using normal LightGBM 4.7.0 registry artifacts with native OpenMP support, and unsupported source fallbacks do not silently inherit the Darwin policy. The project metadata also declares `uv==0.12.0`; invoking it through `uvx` is required because older uv versions can ignore unknown project settings before evaluating that declaration.

Torch and scikit-learn retain their pinned package-contained OpenMP images. LightGBM introduces no third runtime, and the Darwin contract test allowlists exactly those two package-owned images while rejecting Homebrew `libomp`/`libgomp`. Production modules do not set `KMP_DUPLICATE_LIB_OK` or mutate thread-count environment variables at import time; standalone experiments may set explicit thread caps only as resource policy. A standalone `pip install` of the the control-plane runtime wheel does not consume this source/build contract and is therefore not claimed as a safe Darwin arm64 installation path.

## Optional Containers

Additional backends can be enabled via `docker-compose.optional.yml` and the corresponding `.env` adapter variable.

| Container | Image | Ports | Enable by setting |
|-----------|-------|-------|-------------------|
| chromadb | `chromadb/chroma:latest` | 18100:8000 | `FACTORY_KB_ADAPTER=chromadb` + `KB_BACKEND=chromadb` |
| dagster | `dagster/dagster-celery-k8s:latest` | 13000:3000 | `FACTORY_WORKER_BACKEND=dagster` |
| keycloak | `quay.io/keycloak/keycloak:24.0` | 18080:8080 | `FACTORY_AUTH_ADAPTER=keycloak` |
| postgres | `postgres:16-alpine` | 15432:5432 | `FACTORY_STORAGE_ADAPTER=postgres` |
| flet | (built from Dockerfile) | 5002:5002 | Legacy Flet dashboard adapter |

See the brick inventory (`.agents/steering/brick-inventory.md`) for full adapter details.

## Public Datasets

The dataset brick supports ingesting public CAN intrusion detection datasets:

| Dataset | Format | Records | Source |
|---------|--------|---------|--------|
| Car-Hacking | CSV | 2.8M | Hacking/Counter Measurement Lab, Korea |
| OTIDS | Space-delimited TXT | 400K | Open Threat Intelligence Dataset |

These datasets contain raw CAN frames without DBC decoding, making them vehicle-agnostic.
The `csv_can_ingest` adapter handles both formats and yields canonical CAN frame records.

## DBC Decoding

Hyundai/Kia DBC files from the [opendbc](https://github.com/opendbc/opendbc) project decode
Kia public datasets into physical signal values (RPM, throttle, brake pressure, etc.).

```python
# Enable DBC decoding in csv_can_ingest
config = {
    "csv_paths": ["file://data/car_hacking/attack_data.csv"],
    "dbc_path": "file://dbc/hyundai_kia_generic.dbc",
    "source_dataset": "car_hacking",
    "source_vehicle": "kia_soul"
}
```

When `dbc_path` is provided:
- CAN frames are decoded to physical signals using DBC message definitions
- `decoded_signals` and `dbc_message_name` fields are populated
- Downstream profile/synthesize/window/augment stages work with decoded values

When `dbc_path` is omitted:
- Raw bytes mode (original behavior)
- `decoded_signals` and `dbc_message_name` remain `None`
- Suitable for vehicle-agnostic analysis
