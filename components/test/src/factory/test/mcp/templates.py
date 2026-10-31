"""Prompt templates for test MCP prompts."""

PROMPT_TEMPLATES = {
    "run_tests": {
        "description": "Guide for running tests",
        "template": """# Run Tests: {scope}

## Purpose
{purpose}

## Steps

### 1. Discover Tests
```
test_discover(path="{path}")
```

### 2. Run Tests
```
{run_command}
```

### 3. Review Results

Check the output for:
- **passed**: Tests that succeeded
- **failed**: Tests that need attention
- **skipped**: Tests that were skipped

## Troubleshooting

If tests fail:
1. Check the error output
2. Run with verbose=True for details
3. Use `debug_failure` prompt for guidance

## Next Steps

- Fix failing tests
- Add missing test coverage
- Run `foreman_guardian_check` before commit
""",
    },
    "debug_failure": {
        "description": "Guide for debugging test failures",
        "template": """# Debug Test Failure

## Failing Test
- **File**: {test_file}
- **Test**: {test_name}
- **Error**: {error_type}

## Steps

### 1. Get Verbose Output
```
test_run_path(path="{test_file}", verbose=True)
```

### 2. Analyze the Error

{error_analysis}

### 3. Common Fixes

| Error Type | Likely Cause | Fix |
|------------|--------------|-----|
| AssertionError | Wrong expected value | Update assertion |
| ImportError | Missing dependency | Check imports |
| AttributeError | API changed | Update code |
| TimeoutError | Slow test | Optimize or mock |

### 4. Re-run After Fix
```
test_run_path(path="{test_file}")
```

## Prevention

- Write focused unit tests
- Use mocks for external dependencies
- Keep tests fast (<1s each)
""",
    },
    "add_tests": {
        "description": "Guide for adding tests to a component",
        "template": """# Add Tests: {component}

## Test Directory

Create test structure:
```
components/{component}/test/factory/{component}/
├── __init__.py
├── test_core.py
└── test_integration.py
```

## Test Template

```python
\"\"\"Tests for {component} core functionality.\"\"\"

import pytest
from factory.{component}.interface import ...


class Test{ComponentClass}:
    \"\"\"Tests for {ComponentClass}.\"\"\"

    def test_basic_functionality(self):
        \"\"\"Test basic operation.\"\"\"
        # Arrange
        ...
        # Act
        ...
        # Assert
        assert result == expected

    def test_edge_case(self):
        \"\"\"Test edge case handling.\"\"\"
        ...
```

## Run New Tests
```
test_run_component(component_name="{component}")
```

## Coverage Goals

- Core functionality: 80%+
- Edge cases: All documented
- Error handling: All paths
""",
    },
}
