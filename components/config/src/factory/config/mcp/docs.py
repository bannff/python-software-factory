"""Documentation content for config MCP resources."""

CONFIG_DOCS = {
    "overview": {
        "title": "Config Brick Overview",
        "content": """# Config Brick

Centralized configuration with pluggable backends for the Python Factory.

## Core Concepts

- **ConfigStore**: Protocol for key-value configuration storage
- **FeatureFlagStore**: Protocol for feature flag evaluation
- **Adapters**: Pluggable backends (env, file, SSM)
- **Layered Config**: Multiple sources with override precedence

## Quick Start

1. Get a configuration value:
```
config_get(key="database.host", default="localhost")
```

2. Set a configuration value:
```
config_set(key="app.debug", value="true")
```

3. List all keys:
```
config_keys(prefix="database.")
```

## Available Backends

- `env` - Environment variables (default)
- `file` - YAML/JSON file-based configuration
- `ssm` - AWS Systems Manager Parameter Store

## MCP Tools

- `config_get` - Get a configuration value
- `config_set` - Set a configuration value
- `config_delete` - Delete a configuration key
- `config_keys` - List configuration keys
- `config_get_all` - Get all values with prefix
- `config_environment` - Get current environment
- `config_get_aws_identity` - Get active AWS identity (profile, region, account, ARN)
""",
    },
    "adapters": {
        "title": "Config Adapters Guide",
        "content": """# Config Adapters

The config brick uses a ports-and-adapters architecture.

## Environment Adapter (env)

Reads from environment variables.

```python
# Prefix-based namespacing
config = runtime.get_config("env", prefix="MYAPP_")
# MYAPP_DATABASE_HOST -> database.host
```

### Features
- Automatic key transformation (UPPER_SNAKE -> lower.dot)
- Prefix filtering
- Type coercion

## File Adapter (file)

Reads from YAML or JSON files.

```python
config = runtime.get_config("file", path="config/settings.yaml")
```

### Features
- YAML and JSON support
- Nested key access (dot notation)
- Hot reload support

## SSM Adapter (ssm)

Reads from AWS Systems Manager Parameter Store.

```python
config = runtime.get_config("ssm", prefix="/myapp/prod/")
```

### Features
- Secure parameter storage
- IAM-based access control
- Automatic decryption of SecureString

## Layered Configuration

Combine multiple sources with precedence:

```python
runtime.add_layer(runtime.get_config("file", path="defaults.yaml"))
runtime.add_layer(runtime.get_config("env"))  # Overrides file
value = runtime.get_layered("database.host")
```
""",
    },
    "feature-flags": {
        "title": "Feature Flags Guide",
        "content": """# Feature Flags

The config brick supports feature flag evaluation.

## FeatureFlagStore Protocol

```python
class FeatureFlagStore(Protocol):
    def is_enabled(self, flag: str, context: dict | None = None) -> bool: ...
    def get_variant(self, flag: str, context: dict | None = None) -> str | None: ...
    def list_flags(self) -> list[str]: ...
```

## Usage Patterns

### Simple Boolean Flags

```python
if flag_store.is_enabled("new_dashboard"):
    show_new_dashboard()
else:
    show_legacy_dashboard()
```

### Context-Based Evaluation

```python
context = {"user_id": "123", "plan": "enterprise"}
if flag_store.is_enabled("beta_feature", context):
    enable_beta()
```

### A/B Testing Variants

```python
variant = flag_store.get_variant("checkout_flow", context)
if variant == "streamlined":
    use_streamlined_checkout()
elif variant == "classic":
    use_classic_checkout()
```

## Configuration Format

```yaml
feature_flags:
  new_dashboard:
    enabled: true
    rollout_percentage: 50
  beta_feature:
    enabled: true
    allowed_plans: [enterprise, pro]
```
""",
    },
    "aws-identity": {
        "title": "AWS Identity Probe",
        "content": """# AWS Identity Probe

Probes `boto3.Session()` + `sts:GetCallerIdentity` to resolve active
profile, region, account ID, and caller ARN. Cached 5 min. Degrades
gracefully when boto3 is missing or no credentials are configured.

## MCP Tool: `config_get_aws_identity(force_refresh=False)`

Returns: `available`, `profile`, `region`, `account_id`, `identity_arn`,
`user_id`, `error`. Use `force_refresh=True` to bypass TTL cache.

## MCP Resource: `config://aws/identity`

Same identity snapshot as JSON.

## Python API

```python
runtime = ConfigRuntime()
identity = runtime.get_aws_identity()  # cached, force=True bypasses
```

Immutable frozen dataclass. Thread-safe. Returns `available=False`
with error message instead of raising — callers never need try/except.
""",
    },
}
