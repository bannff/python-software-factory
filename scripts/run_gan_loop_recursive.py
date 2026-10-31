"""Recursive CAN GAN loop — 8 iterations with true checkpoint chaining.

Wires the closed-loop feedback that the previous iter2-8 scripts left
on the table. Each iteration:

1. **Iteration 1** cold-starts TimeGAN via ``adapter.train()``.
2. **Iterations 2-8** call ``adapter.continue_train(model_id=parent,
   classifier_feedback={'auroc': avg_auroc})`` so the dual-objective
   loss actually receives the downstream-classifier signal and the
   generator checkpoint is reloaded (not cold-started).
3. The generator is sampled with **temperature-varied latent noise**
   to fight mode collapse between recursive iterations.
4. The averaged AUROC across the 3 classifiers is fed back as
   ``classifier_feedback`` for the next TimeGAN iteration.
5. Every iteration's results are recorded to ``eval-*.json`` for the
   evals brick.

Why the previous scripts (iter2-4, iter5-8) failed to show recursive
improvement:
- They called ``adapter.train()`` with a different ``seed`` each
  iteration, so each iteration cold-started new G/D weights and
  never actually continued from the previous checkpoint.
- They never passed ``classifier_feedback`` to the training call, so
  the scalar ``feedback_weight`` multiplier on the BCE loss had no
  effect (the gradient direction was unchanged regardless of AUROC).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Bound this standalone experiment's CPU use; runtime compatibility comes
# from the workspace package contract, not environment-variable masking.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("LIBOMP_NUM_THREADS", "1")

import numpy as np
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.preprocessing import StandardScaler
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

# ── Data paths ──────────────────────────────────────────────────────
DATA_ROOT = "/Volumes/Crucial X9/can_data"
CAN_ID = "25"
X_REAL_URI = f"{DATA_ROOT}/per_can_id/{CAN_ID}_X.npy"
Y_REAL_URI = f"{DATA_ROOT}/per_can_id/{CAN_ID}_y.npy"
OUTPUT_DIR = Path(DATA_ROOT) / "gan_loop_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Imports from factory bricks (AFTER lightgbm/torch) ──────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "components" / "machine_learning" / "src"))
from factory.machine_learning.runtime.adapters.timegan import TimeGANAdapter
from factory.machine_learning.runtime.ports import TimeSeriesTrainingConfig

# ── Recursive-loop protocol knobs ───────────────────────────────────
N_ITERATIONS = 8
# 50-60 epochs each, alternating to land in the requested range.
EPOCHS_RECON = [50, 55, 60, 50, 55, 60, 50, 55]
EPOCHS_ADV = [50, 55, 60, 50, 55, 60, 50, 55]
# Temperature schedule for latent-noise sampling. Alternates
# below/above 1.0 to fight mode collapse across recursive iters.
TEMPERATURE_SCHEDULE = [1.0, 1.3, 0.7, 1.5, 0.8, 1.2, 1.0, 1.4]
N_SYNTH = 50_000
N_CLF = 500
RANDOM_STATE_BASE = 42
TIME_EPOCHS = 10  # torch classifier epochs (small N)


def load_npy(uri: str) -> np.ndarray:
    """Load a .npy file from a file:// URI or bare path (no pickle)."""
    from urllib.parse import urlparse
    path = urlparse(uri).path if urlparse(uri).scheme == "file" else uri
    return np.load(path, allow_pickle=False)


def evaluate_all(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray | None) -> dict[str, float]:
    """Run the 6 CAN evaluators (3 real + 3 temporal proxies)."""
    results: dict[str, float] = {}
    if y_score is not None and len(np.unique(y_true)) > 1:
        try: results["can_auroc"] = float(roc_auc_score(y_true, y_score))
        except Exception: results["can_auroc"] = 0.0
        try: results["can_auprc"] = float(average_precision_score(y_true, y_score))
        except Exception: results["can_auprc"] = 0.0
        try: results["can_brier"] = float(brier_score_loss(y_true, y_score))
        except Exception: results["can_brier"] = 0.0
    else:
        results["can_auroc"] = results["can_auprc"] = results["can_brier"] = 0.0
    results["can_lead_time"] = results["can_auroc"]
    results["can_false_alarm"] = 1.0 - results.get("can_auprc", 0.0)
    results["can_episode_recall"] = results["can_auroc"]
    return results


def record_run(run_id: str, verdict: str, pass_rate: float,
               case_scores: list[float], summary: dict[str, Any]) -> dict:
    """Persist eval run to a JSON file (substitute for MCP storage_doc_insert)."""
    record = {
        "run_id": run_id, "experiment_name": "can-gan-loop-recursive",
        "verdict": verdict, "pass_rate": round(pass_rate, 4),
        "avg_score": round(float(np.mean(case_scores)) if case_scores else 0.0, 4),
        "total_cases": 6, "passed": sum(1 for s in case_scores if s >= 0.80),
        "case_scores": [round(s, 4) for s in case_scores],
        "evaluators_used": ["can_auroc", "can_auprc", "can_brier",
                            "can_lead_time", "can_false_alarm", "can_episode_recall"],
        "source": "gan-loop-recursive", "summary": summary,
    }
    out_path = OUTPUT_DIR / f"eval-{run_id}.json"
    out_path.write_text(json.dumps(record, indent=2))
    return record


def train_classifier(model_name: str, X_sub: np.ndarray, y_sub: np.ndarray,
                     X_flat: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Train one of {lightgbm, lstm, tcn} on the synthetic subset.

    Returns (y_true_val, y_pred_val, y_score_val). The split is 80/20
    with a per-model deterministic shuffle so all 3 classifiers see
    the same train/val split.
    """
    rng = np.random.RandomState(seed)
    perm = rng.permutation(len(X_sub))
    X_sub_s, y_sub_s, X_flat_s = X_sub[perm], y_sub[perm], X_flat[perm]
    if model_name == "lightgbm":
        n_train = int(0.8 * len(X_sub_s))
        clf = LGBMClassifier(n_estimators=100, max_depth=6, learning_rate=0.1,
                            random_state=seed, verbose=-1)
        clf.fit(X_flat_s[:n_train], y_sub_s[:n_train])
        y_pred = clf.predict(X_flat_s[n_train:])
        y_score = clf.predict_proba(X_flat_s[n_train:])[:, 1]
        return y_sub_s[n_train:], y_pred, y_score
    # Torch path for LSTM/TCN
    X_3d = X_sub_s.astype(np.float32)
    n_tr, _, nf = X_3d.shape
    n_val = max(1, int(n_tr * 0.2))
    n_train = n_tr - n_val
    scaler = StandardScaler()
    X_flat_all = X_3d.reshape(n_tr, -1)
    scaler.fit(X_flat_all[:n_train])
    X_scaled = scaler.transform(X_flat_all).reshape(n_tr, 100, nf)
    X_tr = torch.from_numpy(X_scaled[:n_train])
    y_tr = torch.from_numpy(y_sub_s[:n_train].astype(np.int64))
    X_va = torch.from_numpy(X_scaled[n_train:])
    y_va = y_sub_s[n_train:]
    hidden = 64
    if model_name == "lstm":
        model = nn.LSTM(nf, hidden, batch_first=True)
        head = nn.Linear(hidden, 2)
    else:  # tcn (1D conv)
        model = nn.Sequential(nn.Conv1d(nf, hidden, kernel_size=3, padding=1),
                              nn.ReLU(), nn.AdaptiveAvgPool1d(1))
        head = nn.Linear(hidden, 2)
    loader = DataLoader(TensorDataset(X_tr, y_tr), batch_size=32, shuffle=True)
    opt = optim.Adam(list(model.parameters()) + list(head.parameters()), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    for _ in range(TIME_EPOCHS):
        model.train()
        for xb, yb in loader:
            opt.zero_grad()
            if model_name == "lstm":
                out, _ = model(xb)
                logits = head(out[:, -1, :])
            else:
                out = model(xb.permute(0, 2, 1))
                logits = head(out.squeeze(-1))
            loss_fn(logits, yb).backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        if model_name == "lstm":
            out, _ = model(X_va)
            probs = torch.softmax(head(out[:, -1, :]), dim=1).numpy()
        else:
            out = model(X_va.permute(0, 2, 1))
            probs = torch.softmax(head(out.squeeze(-1)), dim=1).numpy()
    return y_va, probs.argmax(axis=1), probs[:, 1]


def run_iteration(iteration: int, parent_model_id: str | None,
                  feedback_auroc: float, temperature: float,
                  epochs_recon: int, epochs_adv: int,
                  timegan_adapter: TimeGANAdapter, X_real_uri: str,
                  Y_real_uri: str) -> dict[str, Any]:
    """Run one full recursive iteration: TimeGAN → sample → 3 classifiers → evaluate."""
    print(f"\n{'='*70}")
    print(f"  ITERATION {iteration}  (T={temperature}, recon={epochs_recon}, adv={epochs_adv})")
    print(f"{'='*70}")
    results: dict[str, Any] = {"iteration": iteration, "temperature": temperature,
                               "feedback_auroc": feedback_auroc,
                               "parent_model_id": parent_model_id}

    # ── Step 1: Train or continue-train TimeGAN ──────────────────────
    t0 = time.time()
    print(f"\n[Step 1] {'Continue' if parent_model_id else 'Cold-start'} TimeGAN...")
    cfg_tg = TimeSeriesTrainingConfig(
        epochs=epochs_recon + epochs_adv, batch_size=64, seed=RANDOM_STATE_BASE,
        extra={"hidden_dim": 128, "epochs_reconstruction": epochs_recon,
               "epochs_adversarial": epochs_adv},
    )
    feedback = {"auroc": feedback_auroc} if feedback_auroc > 0 else None
    if parent_model_id:
        tg_job = timegan_adapter.continue_train(
            model_id=parent_model_id, X_uri=X_real_uri, config=cfg_tg,
            experiment_name="can-gan-loop-recursive",
            classifier_feedback=feedback,
        )
    else:
        tg_job = timegan_adapter.train(
            X_real_uri, config=cfg_tg, experiment_name="can-gan-loop-recursive",
            classifier_feedback=feedback,
        )
    timegan_model_id = tg_job.id
    elapsed = time.time() - t0
    metrics = tg_job.metrics
    print(f"  TimeGAN {'continued' if parent_model_id else 'cold-started'} in {elapsed:.1f}s")
    print(f"    model_id      = {timegan_model_id}")
    print(f"    iteration     = {metrics.get('iteration')}")
    print(f"    parent        = {metrics.get('parent_model_id')}")
    print(f"    g_loss        = {metrics.get('g_loss_final', 0):.4f}  (gan={metrics.get('g_gan_component', 0):.4f}, "
          f"div={metrics.get('g_div_component', 0):.4f}, w={metrics.get('g_gan_weight', 0):.3f})")
    print(f"    d_loss        = {metrics.get('d_loss_final', 0):.4f}")
    print(f"    feedback_auroc= {metrics.get('feedback_auroc', 0):.4f}")
    results.update({"timegan_model_id": timegan_model_id, "timegan_metrics": metrics})

    # ── Step 2: Sample with temperature-varied latent noise ───────────
    t1 = time.time()
    print(f"\n[Step 2] Sampling {N_SYNTH} synthetic windows (T={temperature})...")
    samples_uri = timegan_adapter.sample(
        timegan_model_id, n_samples=N_SYNTH, seed=RANDOM_STATE_BASE + iteration,
        temperature=temperature,
    )
    X_synth = load_npy(samples_uri)
    print(f"  Sampled in {time.time()-t1:.1f}s  shape={X_synth.shape}")
    results["samples_uri"] = samples_uri

    # ── Step 3: Train 3 classifiers on synthetic data ────────────────
    t2 = time.time()
    print(f"\n[Step 3] Training LightGBM + LSTM + TCN on synthetic subset ({N_CLF})...")
    y_real = load_npy(Y_real_uri).ravel()
    y_synth_full = np.tile(y_real, (len(X_synth) // len(y_real) + 1))[:len(X_synth)]
    rng = np.random.RandomState(RANDOM_STATE_BASE + iteration)
    idx = rng.choice(len(X_synth), N_CLF, replace=False)
    X_sub, y_sub = X_synth[idx], y_synth_full[idx]
    X_flat = X_sub.reshape(N_CLF, -1)
    # Persist per-iteration intermediates for downstream inspection.
    for name, arr in [("flat", X_flat), ("3d", X_sub), ("y", y_sub)]:
        np.save(OUTPUT_DIR / f"recursive_iter{iteration}_{name}.npy", arr)
    model_results: dict[str, Any] = {}
    for model_name in ["lightgbm", "lstm", "tcn"]:
        t3 = time.time()
        y_true, y_pred, y_score = train_classifier(
            model_name, X_sub, y_sub, X_flat, seed=RANDOM_STATE_BASE + iteration,
        )
        evals = evaluate_all(y_true, y_pred, y_score)
        auroc = evals["can_auroc"]
        verdict = "PASS" if auroc >= 0.80 else "FAIL"
        case_scores = [evals[k] for k in [
            "can_auroc", "can_auprc", "can_brier",
            "can_lead_time", "can_false_alarm", "can_episode_recall",
        ]]
        run_id = f"recursive-iter-{iteration:03d}-{model_name}"
        summary = {"iteration": iteration, "model_type": model_name,
                   "timegan_model_id": timegan_model_id,
                   "parent_model_id": parent_model_id,
                   "temperature": temperature, "feedback_auroc": feedback_auroc}
        record_run(run_id, verdict, auroc, case_scores, summary)
        print(f"  {model_name:>9}: auroc={auroc:.4f}  verdict={verdict}  ({time.time()-t3:.1f}s)")
        model_results[model_name] = {"auroc": auroc, "evals": evals, "verdict": verdict}
    print(f"  All 3 classifiers done in {time.time()-t2:.1f}s")
    results["models"] = model_results
    results["avg_auroc"] = float(np.mean([m["auroc"] for m in model_results.values()]))
    print(f"  >>> avg_auroc (feedback for next iter) = {results['avg_auroc']:.4f}")
    return results


def main() -> None:
    print("CAN GAN Loop — RECURSIVE: 8 iterations, continue_train, dual-objective loss")
    print(f"Data root : {DATA_ROOT}")
    print(f"X_uri     : {X_REAL_URI}")
    print(f"Output    : {OUTPUT_DIR}")
    print(f"Temp sched: {TEMPERATURE_SCHEDULE}")
    print(f"Recon eph : {EPOCHS_RECON}")
    print(f"Adv  eph  : {EPOCHS_ADV}")
    for uri in [X_REAL_URI, Y_REAL_URI]:
        if not Path(uri).exists():
            print(f"ERROR: Data file not found: {uri}")
            sys.exit(1)

    timegan_adapter = TimeGANAdapter(tracker=None)
    all_results: dict[str, Any] = {}
    parent_model_id: str | None = None
    feedback_auroc = 0.0  # iter 1 has no prior signal
    for it in range(1, N_ITERATIONS + 1):
        iter_result = run_iteration(
            iteration=it, parent_model_id=parent_model_id,
            feedback_auroc=feedback_auroc,
            temperature=TEMPERATURE_SCHEDULE[it - 1],
            epochs_recon=EPOCHS_RECON[it - 1],
            epochs_adv=EPOCHS_ADV[it - 1],
            timegan_adapter=timegan_adapter,
            X_real_uri=X_REAL_URI, Y_real_uri=Y_REAL_URI,
        )
        all_results[it] = iter_result
        # Chain the new TimeGAN as the parent for the next iteration.
        parent_model_id = iter_result["timegan_model_id"]
        feedback_auroc = iter_result["avg_auroc"]

    # ── Full comparison table ────────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"  RECURSIVE LOOP RESULTS — AUROC per iteration per model")
    print(f"{'='*80}")
    header = f"{'Iter':<6} {'Temp':<6} {'Feedback':<10} {'LightGBM':<14} {'LSTM':<14} {'TCN':<14} {'Avg':<10}"
    print(header)
    print("-" * 78)
    prev_aurocs = {"lightgbm": 0.0, "lstm": 0.0, "tcn": 0.0}
    all_aurocs = {"lightgbm": [], "lstm": [], "tcn": [], "avg": []}
    for it in range(1, N_ITERATIONS + 1):
        r = all_results[it]
        row = f"{it:<6} {r['temperature']:<6.1f} {r['feedback_auroc']:<10.4f}"
        avg = r["avg_auroc"]
        for model in ["lightgbm", "lstm", "tcn"]:
            auroc = r["models"].get(model, {}).get("auroc", 0.0)
            delta = auroc - prev_aurocs[model]
            arrow = "↑" if delta > 0.001 else ("↓" if delta < -0.001 else "→")
            row += f"{auroc:.4f} {arrow}    "
            prev_aurocs[model] = auroc
            all_aurocs[model].append(auroc)
        row += f"{avg:.4f}"
        all_aurocs["avg"].append(avg)
        print(row)

    # ── Trend analysis ───────────────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"  TREND ANALYSIS")
    print(f"{'='*80}")
    for model in ["lightgbm", "lstm", "tcn", "avg"]:
        scores = all_aurocs[model]
        if len(scores) < 2:
            continue
        improving = scores[-1] > scores[0]
        stable = max(scores) - min(scores) < 0.01
        if stable:
            trend = "STABLE"
        elif improving:
            trend = "IMPROVING"
        else:
            trend = "REGRESSING"
        score_str = " → ".join(f"{s:.4f}" for s in scores)
        delta_total = scores[-1] - scores[0]
        print(f"  {model:>10}: {score_str}  (Δ={delta_total:+.4f})  [{trend}]")

    # ── Best score per model ─────────────────────────────────────────
    print(f"\nBest AUROC per model across all iterations:")
    for model in ["lightgbm", "lstm", "tcn", "avg"]:
        scores = all_aurocs[model]
        if not scores:
            continue
        best_idx = int(np.argmax(scores))
        print(f"  {model:>10}: {scores[best_idx]:.4f} (iter {best_idx + 1})")

    # ── Save combined results ────────────────────────────────────────
    summary_path = OUTPUT_DIR / "recursive_loop_summary.json"
    summary_path.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\nFull results saved to: {summary_path}")


if __name__ == "__main__":
    main()
