# Companion-X container — unified MCP + REST + AG-UI server (Docker Compose)
#
# Builder stage builds a polylith wheel (hatch-polylith-bricks bundles all
# bricks into a single ~1MB .whl). Runtime stage installs only the wheel —
# no monorepo source in the final image.
#
# syntax=docker/dockerfile:1.7
# Build context: repo root (.)
# Usage: docker build -f projects/companion_x/Dockerfile -t companion-x .

FROM public.ecr.aws/docker/library/python:3.12-slim AS builder
WORKDIR /build

# Native extensions in the project dependency graph (for example zstd via
# asammdf on arm64) need a compiler and libzstd headers at image-build time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config libzstd-dev && \
    rm -rf /var/lib/apt/lists/*

# Install build tooling
RUN pip install --no-cache-dir uv==0.12.0 hatchling hatch-polylith-bricks

# Resolve and install the locked third-party runtime graph before copying source.
# This layer changes only when pyproject.toml or uv.lock changes; the cache mount
# also avoids re-downloading packages if the layer is invalidated.
COPY pyproject.toml uv.lock /build/
# The root lock validates the full `projects/*` workspace, so retain all
# workspace manifests here while still deferring every project's source copy.
# `projects/circuitron` is NOT a workspace member (root pyproject.toml
# [tool.uv.workspace].exclude, no uv.lock references) — do not COPY it.
COPY projects/companion_x/pyproject.toml /build/projects/companion_x/pyproject.toml
COPY projects/openarcade/pyproject.toml /build/projects/openarcade/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --project projects/companion_x --no-emit-project --no-dev --locked \
        --no-hashes --output-file /tmp/requirements.txt && \
    uv pip install --system -r /tmp/requirements.txt

# Copy the Polylith sources only after third-party dependencies are cached.
COPY BRICKS_INDEX.yaml /build/BRICKS_INDEX.yaml
COPY components/ /build/components/
COPY bases/ /build/bases/
COPY projects/companion_x/ /build/projects/companion_x/

# Hatch-polylith-bricks materializes the local project wheel.  Its source layer
# is intentionally separate from the dependency layer above.
RUN uv build --wheel projects/companion_x --out-dir /build/dist
RUN uv pip install --system --no-deps /build/dist/companion_x-*.whl

# ---------------------------------------------------------------------------
FROM public.ecr.aws/docker/library/python:3.12-slim AS runtime
WORKDIR /app

# Install Docker CLI for sandbox adapter (talks to host Docker via mounted socket)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && \
    curl -fsSL https://download.docker.com/linux/static/stable/$(uname -m)/docker-27.5.1.tgz \
    | tar xz --strip-components=1 -C /usr/local/bin docker/docker && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Copy installed packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages \
                    /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy runtime assets (entrypoint, main, brick index for discovery)
COPY BRICKS_INDEX.yaml /app/BRICKS_INDEX.yaml
COPY projects/companion_x/pyproject.toml /app/pyproject.toml
COPY projects/companion_x/entrypoint.sh /app/entrypoint.sh
COPY projects/companion_x/main.py /app/main.py
# Do not COPY config/backends/ or config/metrics/: neither is tracked in the
# repo. The bricks create them on first runtime access (auth seeds
# config/backends/memory.yaml, metrics creates config/metrics/).
# config/settings.yaml is untracked deployment state (projects/*/config/ is
# gitignored, issue #34), so only the tracked template ships; entrypoint.sh
# seeds the live file from it at start when absent.
COPY projects/companion_x/config/settings.yaml.example /app/config/settings.yaml.example
COPY projects/companion_x/telemetry/exporters/ /app/telemetry/exporters/
COPY projects/companion_x/telemetry/settings.yaml /app/telemetry/settings.yaml
RUN chmod +x /app/entrypoint.sh

ENV WORKSPACE_ROOT=/app
ENV RUN_MODE=api
ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
ENV FASTMCP_LOG_LEVEL=WARNING

# Infrastructure discovery: bricks resolve backends via config brick's
# layered config (InfraEnv → SSM → defaults). No hardcoded backend env
# vars needed — SSM params at /art/support/* provide Neo4j URI etc.
# Set AWS_REGION so the SSM adapter knows where to look.
ENV AWS_REGION=us-east-1

EXPOSE 8000 5001 5002
ENTRYPOINT ["/app/entrypoint.sh"]
