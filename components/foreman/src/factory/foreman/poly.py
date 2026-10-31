import subprocess
from typing import Any

def run_poly_command(args: list[str]) -> dict[str, Any]:
    """Run a polylith command and return output."""
    try:
        result = subprocess.run(
            ["uv", "run", "poly"] + args,
            capture_output=True,
            text=True,
            check=False
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
