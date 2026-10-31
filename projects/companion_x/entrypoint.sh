#!/bin/sh
# Companion-X container entrypoint — supports multiple run modes.
#
# RUN_MODE controls which process starts:
#   unified — unified MCP+API server (default, same as api)
#   api     — alias for unified
#   mcp     — MCP aggregator server (stdio)
#   worker  — SQS long-poll worker (Fargate)
#
# Worker mode requires: SQS_QUEUE_URL, optionally AWS_REGION (default us-east-1)

set -e

# Seed the live workflow config from the tracked template shipped in the image
# (issue #34): `projects/*/config/` is untracked deployment state, so the image
# carries only `settings.yaml.example`. A deployment that supplies its own
# settings.yaml (env_file or bind mount) is left untouched. A repo-relative
# WORKFLOW_CONFIG_DIR from the env_file is anchored at /app — the same
# CWD-relative resolution main.py applies when the var is absent.
WORKFLOW_CONFIG_DIR="${WORKFLOW_CONFIG_DIR:-/app/config}"
case "$WORKFLOW_CONFIG_DIR" in
  /*) ;;
  *) WORKFLOW_CONFIG_DIR="/app/$WORKFLOW_CONFIG_DIR" ;;
esac
if [ ! -f "$WORKFLOW_CONFIG_DIR/settings.yaml" ]; then
  if [ ! -f /app/config/settings.yaml.example ]; then
    echo "ERROR: template /app/config/settings.yaml.example is missing from the image and $WORKFLOW_CONFIG_DIR/settings.yaml does not exist" >&2
    exit 1
  fi
  mkdir -p "$WORKFLOW_CONFIG_DIR"
  cp /app/config/settings.yaml.example "$WORKFLOW_CONFIG_DIR/settings.yaml"
  echo "entrypoint: no live settings.yaml found; seeded $WORKFLOW_CONFIG_DIR/settings.yaml from the tracked template (execution engines langgraph + migration_import REGISTERED)" >&2
fi
export WORKFLOW_CONFIG_DIR

RUN_MODE="${RUN_MODE:-api}"

case "$RUN_MODE" in
  unified|api)
    exec python /app/main.py
    ;;
  mcp)
    export EAGER_LOAD=1
    exec python -c "from factory.mcp_server.core import main; main()"
    ;;
  worker)
    if [ -z "$SQS_QUEUE_URL" ]; then
      echo "ERROR: SQS_QUEUE_URL required for worker mode" >&2
      exit 1
    fi
    exec python -c "
from factory.worker.runtime.runtime import get_runtime
rt = get_runtime(backend='fargate_sqs', broker_url='${SQS_QUEUE_URL}')
rt.start()
"
    ;;
  *)
    echo "ERROR: Unknown RUN_MODE=$RUN_MODE (expected: unified, api, mcp, worker)" >&2
    exit 1
    ;;
esac
