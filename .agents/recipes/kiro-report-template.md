# Kiro Security Report Template

Standard report format for all Kiro SAST/DAST workflow experiments.
Used by scanner, consolidator, validator, and DAST tester skills.

## Pipeline Execution Summary

```
PIPELINE EXECUTION SUMMARY
══════════════════════════
Run ID:          {run_id}
Target:          {target_app} ({framework})
Vuln Class:      {vuln_class}
Scan Type:       SAST | DAST | SAST+DAST
Timestamp:       {iso_timestamp}

Endpoints discovered:    N ({framework}: N)
Params classified:       N user_controlled, N subject_derived, N system
Traced paths:            N (sink_reached: N, auth_gap: N)
Auth patterns detected:  N
Confidence breakdown:    {Confirmed: N, Likely_Vulnerable: N, Weak_Suspicious: N, Medium_Safe: N, Strong_Safe: N}
```

## Finding Categories

```
FINDING CATEGORIES
══════════════════
Web-Facing IDOR (actionable):           N
Service Layer (no object auth):         N
Medium/Strong Safe (auth detected):     N
Needs Review:                           N
Rejected:                               N
```

## Per-Finding Detail

```
PER-FINDING DETAIL
══════════════════

[1] GET /IDOR/profile/{userId}
    File:        IDORViewOtherProfile.java:28-35
    Function:    completed
    CWE:         CWE-639
    Parameter:   userId (PathVariable, user_controlled)
    Confidence:  Likely_Vulnerable (score: 0.85)
    Sink:        repository.findById @ UserRepository.java:42
    Operation:   read (orm_lookup)
    Taint trace: @PathVariable(userId) → completed(userId) → repository.findById(userId) (3 hops, auth_gap: yes)
    Auth checks: [] (none found)
    Dynamic:     awaiting_dynamic_verification | verified_finding | verification_failed
    Impact:      Any authenticated user can read any other user's profile by guessing/enumerating userId
    Attack chain:
      1. Attacker authenticates as user-B
      2. Sends GET /IDOR/profile/{userA-id}
      3. userId flows to repository.findById without ownership check
      4. Returns user-A profile data
    Recommended test: Send GET /IDOR/profile/{userA-id} with user-B token, expect 403
```

## Dynamic Verification Summary (DAST runs only)

```
DYNAMIC VERIFICATION SUMMARY
═════════════════════════════
verified_finding:                  N
verification_failed:               N
partial_verification:              N
awaiting_dynamic_verification:     N

SAST Correlation:
  Predictions confirmed:           N / M
  False predictions:               N
  Novel (DAST-only) findings:      N
```

## Per-Exploit Detail (DAST runs only)

```
[1] GET /IDOR/profile/{userId} — VERIFIED
    Request:  curl -s -H "Authorization: Bearer eyJ...B" http://localhost:8080/IDOR/profile/user-A-id
    Response: 200 OK
      Content-Type: application/json
      Body: {"userId":"user-A-id","name":"Alice","email":"alice@example.com"}
    Expected: 403 Forbidden
    SAST correlation: suspected-vuln-{sast_run_id}-1 (Likely_Vulnerable) — prediction correct
```

## JSON Schema

Findings array for machine consumption:

```json
{
  "run_id": "kiro-sast-webgoat-003",
  "scan_type": "SAST",
  "target": {"app": "webgoat", "framework": "spring_mvc", "files_scanned": 8},
  "summary": {
    "endpoints_discovered": 5,
    "params_classified": {"user_controlled": 3, "subject_derived": 1, "system": 1},
    "traced_paths": 4,
    "auth_patterns": 1,
    "confidence_breakdown": {"Likely_Vulnerable": 3, "Weak_Suspicious": 1}
  },
  "findings": [
    {
      "id": "suspected-vuln-kiro-sast-webgoat-003-1",
      "cwe": "CWE-639",
      "vuln_class": "IDOR",
      "file": "IDORViewOtherProfile.java",
      "function": "completed",
      "line_start": 28,
      "line_end": 35,
      "code_snippet": "...",
      "endpoint": {
        "method": "GET",
        "path": "/IDOR/profile/{userId}",
        "params": [{"name": "userId", "type": "PathVariable", "classification": "user_controlled"}]
      },
      "taint_trace": {
        "hops": ["@PathVariable(userId)", "completed(userId)", "repository.findById(userId)"],
        "hop_count": 3,
        "sink_reached": true,
        "auth_gap": true,
        "auth_checks": []
      },
      "confidence_level": "Likely_Vulnerable",
      "confidence_score": 0.85,
      "sink": {"function": "repository.findById", "file": "UserRepository.java", "line": 42},
      "attack_chain": "1. Attacker authenticates as user-B\n2. Sends GET /IDOR/profile/{userA-id}\n3. userId flows to repository.findById without ownership check\n4. Returns user-A profile data",
      "dynamic_verification_status": "awaiting_dynamic_verification",
      "impact": "Any authenticated user can read any other user's profile",
      "recommended_test": "Send GET /IDOR/profile/{userA-id} with user-B token, expect 403"
    }
  ],
  "dynamic_verification": {
    "verified_finding": 0,
    "verification_failed": 0,
    "awaiting_dynamic_verification": 3,
    "sast_correlation": {"confirmed": 0, "false_predictions": 0, "novel": 0}
  }
}
```

## Usage

- SAST scanner: populate `summary`, `findings` with taint_trace + confidence_level
- DAST tester: populate `dynamic_verification`, update finding status, add http_request/response
- Consolidator: merge multi-agent findings, apply voting, set final confidence
- Validator: update verdicts (CONFIRMED/NEEDS_REVIEW/REJECTED)
- Post-workflow: feed to `games_process_workflow_rl` for GT scoring + blockchain reward
