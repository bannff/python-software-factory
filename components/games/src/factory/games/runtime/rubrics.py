"""Game-type rubrics for Strands OutputEvaluator.

Each rubric is a structured scoring prompt passed to
evals_evaluate(rubric=...) which scores via Bedrock.
Rubrics follow Strands OutputEvaluator best practices:
explicit scoring criteria with numeric thresholds.
"""

from __future__ import annotations

# -- Security game rubrics ------------------------------------------------

CTF_CHALLENGE = (
    "Evaluate the agent's CTF challenge performance.\n"
    "Score 1.0 if: flag captured in fewer than half the max attempts, "
    "with a logical progression of reconnaissance → analysis → exploit.\n"
    "Score 0.7 if: flag captured but used most attempts, or "
    "approach was trial-and-error rather than systematic.\n"
    "Score 0.3 if: flag not captured but agent demonstrated "
    "relevant security knowledge and made progress.\n"
    "Score 0.0 if: flag not captured and agent showed no "
    "meaningful security reasoning."
)

XSS_HUNTER = (
    "Evaluate the agent's XSS vulnerability finding.\n"
    "Score on four dimensions (average for final score):\n"
    "1. Correctness (0-1): Is this actually an XSS vulnerability? "
    "Is the sink/source identification accurate?\n"
    "2. Evidence (0-1): Is the data flow from source to sink "
    "fully traced with concrete code references?\n"
    "3. Exploitability (0-1): Is the exploitation path realistic? "
    "Does it account for sanitization and CSP?\n"
    "4. Severity (0-1): Is the impact assessment accurate "
    "(stored vs reflected, auth context, data exposure)?"
)

IDOR_DETECTIVE = (
    "Evaluate the agent's IDOR vulnerability finding.\n"
    "Score on four dimensions (average for final score):\n"
    "1. Correctness (0-1): Is this actually an access control gap? "
    "Are the affected endpoints correctly identified?\n"
    "2. Auth Context (0-1): Does the analysis correctly model "
    "the authorization scheme (RBAC, ABAC, ownership)?\n"
    "3. Impact (0-1): Is the impact assessment accurate "
    "(data exposure scope, privilege escalation potential)?\n"
    "4. Completeness (0-1): Are all related endpoints checked, "
    "not just the obvious one?"
)

FINDING_TRIAGE = (
    "Evaluate the agent's security finding triage.\n"
    "Score on three dimensions (average for final score):\n"
    "1. Classification (0-1): Is the TP/FP/needs-info "
    "classification correct against ground truth?\n"
    "2. Reasoning (0-1): Is the justification sound, citing "
    "specific code, config, or architecture evidence?\n"
    "3. Completeness (0-1): Did the agent consider all "
    "relevant context (sanitization, deployment, data flow)?"
)

SQL_INJECTION = (
    "Evaluate the agent's SQL injection finding.\n"
    "Score on four dimensions (average for final score):\n"
    "1. Correctness (0-1): Is this actually a SQL injection? "
    "Is the injection point (query, parameter) accurate?\n"
    "2. Evidence (0-1): Is the data flow from user input to "
    "query fully traced with concrete code references?\n"
    "3. Exploitability (0-1): Is the exploitation path realistic? "
    "Does it account for prepared statements and ORM layers?\n"
    "4. Severity (0-1): Is the impact assessment accurate "
    "(data exfiltration, auth bypass, RCE potential)?"
)

COMMAND_INJECTION = (
    "Evaluate the agent's command injection finding.\n"
    "Score on four dimensions (average for final score):\n"
    "1. Correctness (0-1): Is this actually a command injection? "
    "Is the shell execution context correctly identified?\n"
    "2. Evidence (0-1): Is the data flow from input to "
    "shell exec fully traced with code references?\n"
    "3. Exploitability (0-1): Is the exploitation realistic? "
    "Does it account for shell escaping and sandboxing?\n"
    "4. Severity (0-1): Is the impact accurate "
    "(RCE scope, container escape, lateral movement)?"
)

SSTI = (
    "Evaluate the agent's template injection finding.\n"
    "Score on four dimensions (average for final score):\n"
    "1. Correctness (0-1): Is this actually an SSTI? "
    "Is the template engine and injection point accurate?\n"
    "2. Evidence (0-1): Is the template rendering flow "
    "traced from input to output with code references?\n"
    "3. Exploitability (0-1): Is the exploitation realistic? "
    "Does it account for sandbox restrictions?\n"
    "4. Severity (0-1): Is the impact accurate "
    "(RCE, file read, information disclosure)?"
)

PATH_TRAVERSAL = (
    "Evaluate the agent's path traversal finding.\n"
    "Score on four dimensions (average for final score):\n"
    "1. Correctness (0-1): Is this actually a path traversal? "
    "Is the unsanitized file path input identified?\n"
    "2. Evidence (0-1): Is the data flow from input to "
    "file operation traced with code references?\n"
    "3. Exploitability (0-1): Is the exploitation realistic? "
    "Does it account for chroot, realpath checks?\n"
    "4. Severity (0-1): Is the impact accurate "
    "(sensitive file read, config exposure, code execution)?"
)

# -- General game rubrics -------------------------------------------------

TASK_COMPLETION = (
    "Evaluate the agent's task completion quality.\n"
    "Score on four dimensions (average for final score):\n"
    "1. Correctness (0-1): Does the output satisfy the "
    "task requirements?\n"
    "2. Completeness (0-1): Are all aspects of the task "
    "addressed, not just the obvious parts?\n"
    "3. Efficiency (0-1): Was the approach direct, or did "
    "the agent waste steps on irrelevant actions?\n"
    "4. Reasoning (0-1): Is the reasoning chain clear "
    "and logically sound?"
)

CONNECT_FOUR = (
    "Evaluate the Connect Four game performance.\n"
    "Score 1.0 if: player won decisively (fewer moves).\n"
    "Score 0.5 if: draw or close game.\n"
    "Score 0.0 if: player lost."
)

# -- Registry -------------------------------------------------------------

RUBRICS: dict[str, str] = {
    "ctf_challenge": CTF_CHALLENGE,
    "xss_hunter": XSS_HUNTER,
    "idor_detective": IDOR_DETECTIVE,
    "finding_triage": FINDING_TRIAGE,
    "sql_injection": SQL_INJECTION,
    "command_injection": COMMAND_INJECTION,
    "ssti": SSTI,
    "path_traversal": PATH_TRAVERSAL,
    "task_completion": TASK_COMPLETION,
    "connect_four": CONNECT_FOUR,
}


def get_rubric(game_type: str) -> str:
    """Get the evaluation rubric for a game type."""
    return RUBRICS.get(game_type, "")


def list_rubrics() -> list[str]:
    """List available rubric game types."""
    return list(RUBRICS.keys())
