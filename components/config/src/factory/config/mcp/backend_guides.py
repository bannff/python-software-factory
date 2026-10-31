"""Backend-specific guides for config MCP prompts."""

BACKEND_GUIDES = {
    "env": {
        "setup_guide": "Environment variables require no setup. Set variables with your prefix.",
        "backend_config": """```python
config = runtime.get_config("env", prefix="MYAPP_")
# Access: MYAPP_DATABASE_HOST -> database.host
```""",
    },
    "file": {
        "setup_guide": "Create a YAML or JSON configuration file.",
        "backend_config": """```yaml
# config/settings.yaml
database:
  host: localhost
  port: 5432
app:
  debug: false
```

```python
config = runtime.get_config("file", path="config/settings.yaml")
```""",
    },
    "ssm": {
        "setup_guide": """AWS SSM Parameter Store setup:
1. Configure AWS credentials
2. Create parameters with prefix
3. Grant IAM permissions""",
        "backend_config": """```python
config = runtime.get_config("ssm", prefix="/myapp/prod/", region="us-east-1")
# Access: /myapp/prod/database/host -> database.host
```""",
    },
}
