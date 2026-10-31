import json

updates = {
    "projects/companion_x/runs/vampi-idor-004.json": {
        "precision": 0.6667, "recall": 0.6667, "f1": 0.6667,
        "true_positives": 4, "false_positives": 2, "false_negatives": 2,
        "matched_gt_ids": ["vampi-idor-get-001", "vampi-idor-put-003",
                           "vampi-idor-put-004", "vampi-mass-assign-006"],
        "missed_gt_ids": ["vampi-idor-delete-002", "vampi-sqli-005"],
    },
    "projects/companion_x/runs/warehouse-idor-001.json": {
        "precision": 1.0, "recall": 1.0, "f1": 1.0,
        "true_positives": 3, "false_positives": 0, "false_negatives": 0,
        "matched_gt_ids": ["idor-warehouse-get-001",
                           "idor-warehouse-put-003",
                           "idor-warehouse-delete-002"],
        "missed_gt_ids": [],
    },
    "projects/companion_x/runs/dvwa-idor-001.json": {
        "precision": 0.8, "recall": 0.4, "f1": 0.5333,
        "true_positives": 4, "false_positives": 1, "false_negatives": 6,
        "matched_gt_ids": ["dvwa-sqli", "dvwa-command-injection",
                           "dvwa-file-inclusion", "dvwa-sqli-blind"],
        "missed_gt_ids": ["dvwa-brute-force", "dvwa-csrf",
                          "dvwa-file-upload", "dvwa-insecure-captcha",
                          "dvwa-xss-reflected", "dvwa-xss-stored"],
    },
}

for path, scores in updates.items():
    with open(path) as f:
        report = json.load(f)
    report["automated_scoring"] = {
        "method": "evals_score_gt",
        "scorer_source": "components/evals/src/factory/evals/runtime/gt_scorer.py",
        **scores,
    }
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Updated {path}")
