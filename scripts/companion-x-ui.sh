#!/usr/bin/env bash
# Launch Companion-X API + Next.js UI from anywhere — no containers needed.
#
# Usage: ~/workplace/python-factory/scripts/companion-x-ui.sh
# (or alias it: alias companion-ui='~/workplace/python-factory/scripts/companion-x-ui.sh')
#
# All adapters are container-free (ChromaDB, SQLite, networkx, memory). The
# script always runs from the factory root so file-based storage (ChromaDB
# ./chroma_data, ./chroma_memory, events.db) writes to the correct location.
#
# Ctrl-C stops both processes.

set -euo pipefail

FACTORY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NEXT_DIR="$FACTORY_ROOT/frontends/next-dashboard"
API_PORT="${API_PORT:-8000}"
NEXT_PORT="${NEXT_PORT:-3000}"
ENV_FILE="$FACTORY_ROOT/projects/companion_x/.env"
# Launcher-minted local MCP credential: persisted 0600 so a hand-started
# `next dev` can join this API; gitignored, never a build input, removed by
# cleanup(). MCP_LOCAL_TOKEN_FILE overrides it, resolved after the env file is
# sourced; it must be absolute, because the dashboard resolves a relative value
# against its own cwd.
MCP_TOKEN_FILE_DEFAULT="$FACTORY_ROOT/projects/companion_x/.storage/local-mcp-token"

# Ports 8000/3000 belong to the owner's live Companion-X. An agent (KiroCrew
# goal loop, sub-agent, cron) must smoke-launch on API_PORT=18000 NEXT_PORT=13000.
# Enforce here so a misread doc can never restart the owner's stack under them.
if [[ -n "${KIROCREW_SPAWNED:-}" || -n "${KIROCREW_SESSION_KEY:-}" ]]; then
    if [[ "$API_PORT" == "8000" || "$NEXT_PORT" == "3000" ]]; then
        echo "REFUSED: agent-spawned launch on owner ports (API_PORT=$API_PORT NEXT_PORT=$NEXT_PORT)." >&2
        echo "Agents must use API_PORT=18000 NEXT_PORT=13000 (LOOP-GUIDE safety rail). Nothing was started." >&2
        exit 2
    fi
fi

cleanup() {
    echo ""
    echo "Stopping Companion-X..."
    [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true
    [[ -n "${NEXT_PID:-}" ]] && kill "$NEXT_PID" 2>/dev/null || true
    [[ -n "${API_PID_FILE:-}" ]] && rm -f "$API_PID_FILE"
    [[ -n "${MCP_TOKEN_FILE_CREATED:-}" ]] && rm -f "${MCP_TOKEN_FILE:-}" || true
    wait 2>/dev/null
    echo "Done."
}
trap cleanup EXIT INT TERM HUP QUIT

# Source the env file so adapters resolve correctly. Preserve the
# ambient AWS_PROFILE first — the committed .env ships with
# AWS_PROFILE= (blank) as a template default, and `set -a; source`
# would otherwise unconditionally overwrite a real profile (e.g. one
# refreshed by the credential helper) with that empty string, breaking every AWS SDK
# call in the API process ("config profile () could not be found").
_AMBIENT_AWS_PROFILE="${AWS_PROFILE:-}"
if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
fi
if [[ -z "${AWS_PROFILE:-}" && -n "$_AMBIENT_AWS_PROFILE" ]]; then
    export AWS_PROFILE="$_AMBIENT_AWS_PROFILE"
fi

if [[ -n "${MCP_LOCAL_TOKEN_FILE:-}" && "$MCP_LOCAL_TOKEN_FILE" != /* ]]; then
    echo "MCP_LOCAL_TOKEN_FILE must be an absolute path, e.g. $MCP_TOKEN_FILE_DEFAULT (got: $MCP_LOCAL_TOKEN_FILE)" >&2
    exit 1
fi
MCP_TOKEN_FILE="${MCP_LOCAL_TOKEN_FILE:-$MCP_TOKEN_FILE_DEFAULT}"

# Never mistake a stale API's health response for this launch becoming ready.
# Mirror uvicorn's bind (SO_REUSEADDR, so TIME_WAIT leftovers don't count) and
# give a previous instance that is still draining connections up to 10s to exit
# before declaring the port genuinely taken.
port_free() {
    python3 -c 'import socket,sys
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1",int(sys.argv[1]))); s.close()' "$1" 2>/dev/null
}
for _attempt in $(seq 1 20); do
    port_free "$API_PORT" && break
    [[ $_attempt -eq 1 ]] && echo "API port $API_PORT still held by a previous instance; waiting for it to release..." >&2
    sleep 0.5
done
if ! port_free "$API_PORT"; then
    echo "API port $API_PORT is already in use; stop the owning process or choose API_PORT" >&2
    lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN 2>/dev/null | awk 'NR>1{print "  held by:", $1, "pid", $2}' >&2 || true
    exit 1
fi

# The local UI always uses authenticated MCP through its server-side BFF.
export MCP_LOCAL_AUTH="${MCP_LOCAL_AUTH:-true}"
if [[ ! "$MCP_LOCAL_AUTH" =~ ^(1|true|yes)$ ]]; then
    echo "companion-x-ui.sh requires MCP_LOCAL_AUTH=true" >&2
    exit 1
fi
if [[ -z "${MCP_LOCAL_AUTH_TOKEN:-}" ]]; then
    export MCP_LOCAL_AUTH_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    echo "==> Generated ephemeral local MCP credential"
    # Persist it so a hand-started process can join without this shell. The
    # token goes on stdin (never argv, which `ps` exposes; `python3 -c` keeps
    # the program out of the data path where a heredoc would consume stdin), the
    # opened descriptor is fchmod'ed (a pre-existing or symlinked target cannot
    # keep a looser mode) and the mode is read back from stat.
    MCP_TOKEN_MODE="$(printf '%s' "$MCP_LOCAL_AUTH_TOKEN" | python3 -c '
import os, stat, sys
path = sys.argv[1]
token = sys.stdin.read().strip()
os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
try:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
except OSError as error:
    sys.stderr.write(f"refusing to write the local MCP credential: {error}\n")
    raise SystemExit(1)
os.fchmod(descriptor, 0o600)
with os.fdopen(descriptor, "w") as handle:
    handle.write(token)
mode = stat.S_IMODE(os.stat(path, follow_symlinks=False).st_mode)
if mode != 0o600:
    sys.stderr.write(f"local MCP credential mode is {mode:04o}, expected 0600\n")
    raise SystemExit(1)
print(f"{mode:04o}")
' "$MCP_TOKEN_FILE")" || { echo "ERROR: could not persist the local MCP credential" >&2; exit 1; }
    MCP_TOKEN_FILE_CREATED=1
    echo "==> Persisted the local MCP credential to $MCP_TOKEN_FILE (mode $MCP_TOKEN_MODE)"
elif [[ ${#MCP_LOCAL_AUTH_TOKEN} -lt 16 || ${#MCP_LOCAL_AUTH_TOKEN} -gt 512 \
        || ! "$MCP_LOCAL_AUTH_TOKEN" =~ ^[A-Za-z0-9._~-]+$ ]]; then
    echo "MCP_LOCAL_AUTH_TOKEN must be 16..512 URL-safe characters" >&2
    exit 1
fi

# Encrypted-at-rest stores (Settings -> Secrets, credential slots) fail closed
# without a local key. Mint once and keep it: rotating would orphan stored secrets.
PROTECTED_KEY_EXPORTS="$(python3 "$FACTORY_ROOT/scripts/local_protected_keys.py" \
    "$FACTORY_ROOT/projects/companion_x/.storage/local-protected-keys.json")" \
    || { echo "ERROR: could not provision the local protected-content keys" >&2; exit 1; }
eval "$PROTECTED_KEY_EXPORTS"

# Select the project-owned Workflow engine registry, independent of cwd.
export WORKFLOW_CONFIG_DIR="${WORKFLOW_CONFIG_DIR:-$FACTORY_ROOT/projects/companion_x/config}"
# Fresh clones have no live settings.yaml (projects/*/config/ is untracked
# deployment state, issue #34). Without it the workflow brick registers
# unhealthy with zero tools while /api/health still answers 200, so seed the
# live file from the tracked template exactly like the container entrypoint
# does. An existing settings.yaml (the owner's, on this machine) is never
# touched.
if [[ ! -f "$WORKFLOW_CONFIG_DIR/settings.yaml" ]]; then
    if [[ -f "$WORKFLOW_CONFIG_DIR/settings.yaml.example" ]]; then
        mkdir -p "$WORKFLOW_CONFIG_DIR"
        cp "$WORKFLOW_CONFIG_DIR/settings.yaml.example" "$WORKFLOW_CONFIG_DIR/settings.yaml"
        echo "==> Seeded $WORKFLOW_CONFIG_DIR/settings.yaml from the tracked template (execution engines langgraph + migration_import REGISTERED)"
    else
        echo "ERROR: $WORKFLOW_CONFIG_DIR has no settings.yaml and no settings.yaml.example to seed it from — the workflow brick will not load" >&2
        exit 1
    fi
fi
export EVENTS_BACKEND="${EVENTS_BACKEND:-sqlite}"
export EVENTS_SQLITE_PATH="${EVENTS_SQLITE_PATH:-$FACTORY_ROOT/.storage/events.db}"
export FACTORY_API_PORT="$API_PORT"
export COMPANION_X_LAUNCH_ID="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
API_PID_FILE="$(mktemp -t companion-x-api-pid.XXXXXX)"
export COMPANION_X_API_PID_FILE="$API_PID_FILE"

echo "==> Starting API on :$API_PORT (cwd: $FACTORY_ROOT)"
cd "$FACTORY_ROOT"
uv run python projects/companion_x/main.py > >(sed 's/^/[api] /') 2>&1 &
API_PID=$!

# Readiness deadline is env-tunable: a cold start (uv resolve + 45 bricks) can
# outrun a fixed 30s, and a timeout that only says "not ready" hides whether
# curl failed, the pid file was empty, another instance held the port, or a
# brick registered degraded. Track LAST_REASON per attempt and surface it.
ATTEMPTS="${COMPANION_X_READY_ATTEMPTS:-60}"
# Validate the override like the other env knobs (absolute token path, token
# length/regex, MCP_LOCAL_AUTH): a non-numeric value, or one BSD `seq` would
# count down from (0/-1), silently corrupts the loop and makes the printed
# budget disagree with the attempts actually made. A single regex with no
# arithmetic also rejects padded literals (08/09/007) that bash would evaluate
# as invalid octal. Fall back to the default.
if ! [[ "$ATTEMPTS" =~ ^[1-9][0-9]*$ ]]; then
    ATTEMPTS=60
fi
echo "==> Waiting for API health (up to ${ATTEMPTS}s)..."
API_READY=0
LAST_REASON="no health response yet"
for _ in $(seq 1 "$ATTEMPTS"); do
    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo "API process exited before becoming ready" >&2
        exit 1
    fi
    HEALTH_BODY="$(curl -sf "http://127.0.0.1:$API_PORT/api/health" 2>/dev/null || true)"
    if [[ -z "$HEALTH_BODY" ]]; then
        LAST_REASON="curl unreachable on :$API_PORT"
    elif [[ ! -s "$API_PID_FILE" ]]; then
        LAST_REASON="pid-file empty ($API_PID_FILE)"
    else
        EXPECTED_API_PID="$(cat "$API_PID_FILE")"
        HEALTH_IDENTITY="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(str(d.get("process_id",""))+":"+str(d.get("launch_id","")))' <<<"$HEALTH_BODY" 2>/dev/null || true)"
        if [[ "$HEALTH_IDENTITY" != "$EXPECTED_API_PID:$COMPANION_X_LAUNCH_ID" ]]; then
            LAST_REASON="identity mismatch (got ${HEALTH_IDENTITY:-<none>}, expected $EXPECTED_API_PID:$COMPANION_X_LAUNCH_ID)"
        elif ! python3 -c 'import json,sys; d=json.load(sys.stdin); h=d.get("mcp_health") or {}; sys.exit(0 if d.get("status")=="healthy" and h.get("healthy_bricks")==h.get("total_bricks") else 1)' <<<"$HEALTH_BODY" 2>/dev/null; then
            # #68: identity alone printed "API ready" while a brick registered
            # unhealthy (top-level status was a literal). Gate on the aggregate:
            # status healthy AND every registered brick healthy.
            HEALTH_SUMMARY="$(python3 -c 'import json,sys; d=json.load(sys.stdin); h=d.get("mcp_health") or {}; print("status="+str(d.get("status"))+" bricks="+str(h.get("healthy_bricks"))+"/"+str(h.get("total_bricks")))' <<<"$HEALTH_BODY" 2>/dev/null || true)"
            LAST_REASON="bricks degraded (${HEALTH_SUMMARY:-unparseable health body})"
        else
            API_READY=1
            echo "==> API ready (pid $EXPECTED_API_PID)"
            break
        fi
    fi
    sleep 1
done
if [[ "$API_READY" != 1 ]]; then
    echo "API did not become ready on port $API_PORT after ${ATTEMPTS}s — last state: $LAST_REASON" >&2
    exit 1
fi

echo "==> Starting Next.js on :$NEXT_PORT"
cd "$NEXT_DIR"
API_URL="http://127.0.0.1:$API_PORT" npx next dev --port "$NEXT_PORT" 2>&1 | sed 's/^/[next] /' &
NEXT_PID=$!

echo ""
echo "  Dashboard:  http://localhost:$NEXT_PORT"
echo "              Open that origin. Only its dev-origin allowlist hydrates:"
echo "              localhost, 127.0.0.1, [::1] (GH #142)."
echo "  API:        http://localhost:$API_PORT"
echo "  Adapters:   container-free (ChromaDB, SQLite, networkx, memory)"
echo "  Ctrl-C to stop."
echo ""

wait
