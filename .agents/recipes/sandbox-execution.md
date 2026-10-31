# Recipe: Sandbox Execution

Validates remote execution environment provisioning, command execution, and file transfer.

## Bricks Used
- `sandbox` - Remote execution environments
- `logger` - Logging sandbox operations
- `events` - Event streaming for environment lifecycle

## Scenario

Provision a sandbox environment, execute commands, transfer files, monitor status, and teardown — all with audit logging.

## Prerequisites

- No AWS required (uses MockAdapter)
- Note: Real AWS EC2/SSM adapters require credentials

## Steps

### Step 1: Initialize Bricks

```python
import asyncio
import tempfile
from pathlib import Path

# Sandbox - needs mock adapter
from factory.sandbox.runtime.adapters.mock import MockSandboxAdapter
from factory.sandbox.runtime.runtime import SandboxRuntime
adapter = MockSandboxAdapter()
sandbox = SandboxRuntime(adapter=adapter)

# Logger
tmpdir_log = Path(tempfile.mkdtemp())
from factory.logger.runtime.runtime import LoggerRuntime
logger = LoggerRuntime(log_dir=str(tmpdir_log))

# Events
tmpdir_events = Path(tempfile.mkdtemp())
(tmpdir_events / "subscriptions").mkdir(parents=True, exist_ok=True)
from factory.events.runtime.runtime import EventsRuntime
events = EventsRuntime(config_dir=tmpdir_events)
```

### Step 2: Health Checks

```python
health = sandbox.health_check()
# Returns: {"healthy": True, "adapter": {...}, "active_environments": 0}
```

### Step 3: Provision Environment

```python
from factory.sandbox.runtime.models import SandboxConfig

env = await sandbox.provision(SandboxConfig(
    instance_type="t3.medium",
))
env_id = env.env_id
# Returns: EnvironmentInfo(env_id="...", status=PROVISIONING)
```

### Step 4: Emit Provisioning Event

```python
events.publish(
    event_type="sandbox.provisioned",
    payload={"env_id": env_id, "instance_type": "t3.medium"},
    source="sandbox-brick",
)
```

### Step 5: Check Status

```python
status = await sandbox.get_status(env_id)
# Returns: EnvironmentInfo with updated status, IPs
```

### Step 6: Execute Command

```python
result = await sandbox.execute(
    env_id=env_id,
    command="echo 'Hello from sandbox' && python --version",
    timeout_seconds=60,
)
# Returns: CommandResult(success=True, exit_code=0, stdout="...", stderr="...")
```

### Step 7: Upload File

```python
# Create a temp file to upload
tmpfile = Path(tempfile.mkdtemp()) / "test-script.py"
tmpfile.write_text("print('Hello from uploaded script')")

upload_result = await sandbox.upload_file(
    env_id=env_id,
    local_path=str(tmpfile),
    remote_path="/tmp/test-script.py",
)
```

### Step 8: Execute Uploaded Script

```python
result = await sandbox.execute(
    env_id=env_id,
    command="python /tmp/test-script.py",
    timeout_seconds=30,
)
# Returns: CommandResult with script output
```

### Step 9: Download File

```python
download_path = Path(tempfile.mkdtemp()) / "downloaded.py"
download_result = await sandbox.download_file(
    env_id=env_id,
    remote_path="/tmp/test-script.py",
    local_path=str(download_path),
)
```

### Step 10: Log Activity

```python
logger.info(
    f"Sandbox session completed: {env_id}",
    source="sandbox",
    context={"commands_run": 2, "files_transferred": 2},
)
```

### Step 11: List Environments

```python
envs = sandbox.list_environments()
# Returns: list with our environment
```

### Step 12: Terminate

```python
await sandbox.terminate(env_id)

events.publish(
    event_type="sandbox.terminated",
    payload={"env_id": env_id},
    source="sandbox-brick",
)
```

## Success Criteria

- [x] Environment provisioned
- [x] Commands executed with output captured
- [x] File upload works
- [x] File download works
- [x] Environment status trackable
- [x] Lifecycle events emitted
- [x] Clean termination

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| sandbox | `factory.sandbox.runtime.runtime.SandboxRuntime` | `provision()`, `execute()`, `upload_file()`, `terminate()` |
| sandbox | `factory.sandbox.runtime.models` | `SandboxConfig`, `EnvironmentInfo`, `CommandResult` |
| sandbox | `factory.sandbox.core.EnvironmentStatus` | Enum: PROVISIONING, RUNNING, TERMINATED |
