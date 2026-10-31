import json
from factory.evals.runtime.gt_scorer import score

def run_score(name, findings, gt_path):
    with open(gt_path) as f:
        gt = json.load(f)
    r = score(findings, gt)
    print(f"{name}: P={r['precision']} R={r['recall']} F1={r['f1']} TP={r['true_positives']} FP={r['false_positives_count']} FN={r['false_negatives']}")
    print(f"  Matched: {[m['gt']['gt_id'] for m in r['matched']]}")
    print(f"  Missed: {[m['gt_id'] for m in r['missed']]}")
    return r

v = run_score("VAmPI", [
    {"cwe": "CWE-639", "resource": "GET /users/v1/{username}"},
    {"cwe": "CWE-639", "resource": "PUT /users/v1/{username}/email"},
    {"cwe": "CWE-639", "resource": "PUT /users/v1/{username}/password"},
    {"cwe": "CWE-639", "resource": "GET /users/v1/_debug"},
    {"cwe": "CWE-915", "resource": "POST /users/v1/register"},
    {"cwe": "CWE-639", "resource": "GET /books/v1/{book_title}"},
], "projects/companion_x/challenges/vampi/gt_entries.json")
print()

w = run_score("Warehouse", [
    {"cwe": "CWE-639", "resource": "GET /warehouses/{code}"},
    {"cwe": "CWE-639", "resource": "PUT /warehouses/{code}"},
    {"cwe": "CWE-639", "resource": "DELETE /warehouses/{code}"},
], "projects/companion_x/challenges/idor_warehouse/gt_entries.json")
print()

d = run_score("DVWA", [
    {"cwe": "CWE-89", "resource": "GET /vulnerabilities/sqli/"},
    {"cwe": "CWE-78", "resource": "POST /vulnerabilities/exec/"},
    {"cwe": "CWE-22", "resource": "GET /vulnerabilities/fi/"},
    {"cwe": "CWE-89", "resource": "GET /vulnerabilities/sqli_blind/"},
    {"cwe": "CWE-639", "resource": "GET /hackable/uploads/"},
], "projects/companion_x/challenges/dvwa/gt_entries.json")
