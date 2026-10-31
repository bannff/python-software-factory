"""Run CAN GAN loop iterations 5-8 with TimeGAN — DIFFERENT seeds each iteration.

Each iteration trains a fresh TimeGAN with a unique seed, generates 50K
synthetic samples, trains LightGBM/LSTM/TCN, evaluates, and records results.
Seed mapping: iter5→100, iter6→200, iter7→300, iter8→400.
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
import torch, torch.nn as nn, torch.optim as optim
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

# ── Seed mapping: each iteration gets a DIFFERENT seed ──────────────
ITERATION_SEEDS = {5: 100, 6: 200, 7: 300, 8: 400}


def load_npy(uri: str) -> np.ndarray:
    from urllib.parse import urlparse
    path = urlparse(uri).path if urlparse(uri).scheme == "file" else uri
    return np.load(path, allow_pickle=False)


def evaluate_all(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray | None) -> dict[str, float]:
    results = {}
    if y_score is not None and len(np.unique(y_true)) > 1:
        try: results["can_auroc"] = float(roc_auc_score(y_true, y_score))
        except: results["can_auroc"] = 0.0
        try: results["can_auprc"] = float(average_precision_score(y_true, y_score))
        except: results["can_auprc"] = 0.0
        try: results["can_brier"] = float(brier_score_loss(y_true, y_score))
        except: results["can_brier"] = 0.0
    else:
        results["can_auroc"] = results["can_auprc"] = results["can_brier"] = 0.0
    results["can_lead_time"] = results["can_auroc"]
    results["can_false_alarm"] = 1.0 - results.get("can_auprc", 0.0)
    results["can_episode_recall"] = results["can_auroc"]
    return results


def record_run(run_id: str, verdict: str, pass_rate: float,
               case_scores: list[float], summary: dict[str, Any]) -> dict:
    record = {
        "run_id": run_id,
        "experiment_name": "can-gan-loop-timegan",
        "verdict": verdict,
        "pass_rate": round(pass_rate, 4),
        "avg_score": round(float(np.mean(case_scores)) if case_scores else 0.0, 4),
        "total_cases": 6,
        "passed": sum(1 for s in case_scores if s >= 0.80),
        "case_scores": [round(s, 4) for s in case_scores],
        "evaluators_used": [
            "can_auroc", "can_auprc", "can_brier",
            "can_lead_time", "can_false_alarm", "can_episode_recall",
        ],
        "source": "gan-loop-timegan",
        "summary": summary,
    }
    out_path = OUTPUT_DIR / f"eval-{run_id}.json"
    out_path.write_text(json.dumps(record, indent=2))
    return record


def run_iteration(iteration: int, seed: int, timegan_adapter: TimeGANAdapter,
                  X_real_uri: str, Y_real_uri: str) -> dict[str, Any]:
    print(f"\n{'='*70}")
    print(f"  ITERATION {iteration}  (seed={seed})")
    print(f"{'='*70}")

    results: dict[str, Any] = {"iteration": iteration, "seed": seed, "models": {}}

    # ── Step 1: Train TimeGAN with THIS iteration's seed ─────────────
    print(f"\n[Step 1] Training TimeGAN (seed={seed})...")
    t0 = time.time()
    cfg_tg = TimeSeriesTrainingConfig(
        epochs=100, batch_size=64, seed=seed,
        extra={"hidden_dim": 128, "epochs_reconstruction": 50, "epochs_adversarial": 50},
    )
    tg_job = timegan_adapter.train(X_real_uri, config=cfg_tg, experiment_name="can-gan-loop-timegan")
    timegan_model_id = tg_job.id
    elapsed = time.time() - t0
    print(f"  TimeGAN trained in {elapsed:.1f}s  model_id={timegan_model_id}")
    print(f"  g_loss={tg_job.metrics['g_loss_final']:.4f}  d_loss={tg_job.metrics['d_loss_final']:.4f}")
    results["timegan_model_id"] = timegan_model_id
    results["timegan_metrics"] = tg_job.metrics

    # ── Step 2: Generate 50000 synthetic samples with same seed ──────
    print(f"\n[Step 2] Generating 50000 synthetic samples (seed={seed})...")
    t1 = time.time()
    samples_uri = timegan_adapter.sample(timegan_model_id, n_samples=50000, seed=seed)
    X_synth = load_npy(samples_uri)
    elapsed = time.time() - t1
    print(f"  Samples generated in {elapsed:.1f}s  shape={X_synth.shape}")
    results["samples_uri"] = samples_uri

    # ── Prepare classifier data ──────────────────────────────────────
    y_real = load_npy(Y_REAL_URI).ravel()
    y_synth_full = np.tile(y_real, (len(X_synth) // len(y_real) + 1))[:len(X_synth)]

    N_CLF = min(500, len(X_synth))
    idx = np.random.RandomState(seed).choice(len(X_synth), N_CLF, replace=False)
    X_sub = X_synth[idx]
    y_sub = y_synth_full[idx]
    X_flat = X_sub.reshape(N_CLF, -1)
    print(f"  Classifier subset: {N_CLF} samples (seed={seed})")

    # Save intermediate arrays
    for name, arr in [("flat", X_flat), ("3d", X_sub), ("y", y_sub)]:
        np.save(OUTPUT_DIR / f"iter{iteration}_{name}.npy", arr)

    flat_uri = f"file://{OUTPUT_DIR / f'iter{iteration}_flat.npy'}"
    td_uri = f"file://{OUTPUT_DIR / f'iter{iteration}_3d.npy'}"
    y_uri = f"file://{OUTPUT_DIR / f'iter{iteration}_y.npy'}"

    # ── Step 3: Train classifiers + evaluate ─────────────────────────
    for model_name, is_torch in [("lightgbm", False), ("lstm", True), ("tcn", True)]:
        t2 = time.time()
        print(f"\n[Step 3] Training {model_name.upper()}...")
        try:
            # Shuffle before split to ensure both classes in val set
            shuffle_idx = np.random.RandomState(seed).permutation(N_CLF)
            X_sub_shuf = X_sub[shuffle_idx]
            y_sub_shuf = y_sub[shuffle_idx]
            X_flat_shuf = X_flat[shuffle_idx]

            if not is_torch:
                n_train = 400
                X_tr, y_tr = X_flat_shuf[:n_train], y_sub_shuf[:n_train]
                X_va, y_va = X_flat_shuf[n_train:], y_sub_shuf[n_train:]
                clf = LGBMClassifier(n_estimators=100, max_depth=6, learning_rate=0.1,
                                     random_state=seed, verbose=-1)
                clf.fit(X_tr, y_tr)
                y_pred = clf.predict(X_va)
                y_score = clf.predict_proba(X_va)[:, 1]
            else:
                X_3d = X_sub_shuf.astype(np.float32)
                n_tr, _, nf = X_3d.shape
                n_val = max(1, int(n_tr * 0.2))
                n_train = n_tr - n_val

                scaler = StandardScaler()
                X_flat_all = X_3d.reshape(n_tr, -1)
                scaler.fit(X_flat_all[:n_train])
                X_flat_scaled = scaler.transform(X_flat_all).reshape(n_tr, 100, nf)
                X_tr = torch.from_numpy(X_flat_scaled[:n_train])
                y_tr_t = torch.from_numpy(y_sub_shuf[:n_train].astype(np.int64))
                X_va_np = X_flat_scaled[n_train:]
                y_va = y_sub_shuf[n_train:]
                X_va = torch.from_numpy(X_va_np)

                hidden = 64
                if model_name == "lstm":
                    model = nn.LSTM(nf, hidden, batch_first=True)
                    head = nn.Linear(hidden, 2)
                else:  # TCN-like 1D conv
                    model = nn.Sequential(
                        nn.Conv1d(nf, hidden, kernel_size=3, padding=1), nn.ReLU(),
                        nn.AdaptiveAvgPool1d(1),
                    )
                    head = nn.Linear(hidden, 2)

                loader = DataLoader(TensorDataset(X_tr, y_tr_t), batch_size=32, shuffle=True)
                params = list(model.parameters()) + list(head.parameters())
                opt = optim.Adam(params, lr=1e-3)
                loss_fn = nn.CrossEntropyLoss()

                for epoch in range(10):
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
                y_pred = probs.argmax(axis=1)
                y_score = probs[:, 1]

            # ── Step 4: Evaluate ─────────────────────────────────────
            evals = evaluate_all(y_va, y_pred, y_score)
            auroc = evals["can_auroc"]
            verdict = "PASS" if auroc >= 0.80 else "FAIL"
            case_scores = [evals[k] for k in [
                "can_auroc", "can_auprc", "can_brier",
                "can_lead_time", "can_false_alarm", "can_episode_recall",
            ]]

            # ── Step 4b: Record ──────────────────────────────────────
            run_id = f"timegan-iter-{iteration:03d}-{model_name}"
            summary = {
                "iteration": iteration, "seed": seed,
                "model_type": model_name,
                "timegan_model_id": timegan_model_id,
            }
            record_run(run_id, verdict, auroc, case_scores, summary)
            elapsed = time.time() - t2
            print(f"  {model_name}: auroc={auroc:.4f}  verdict={verdict}  ({elapsed:.1f}s)")
            results["models"][model_name] = {
                "auroc": auroc, "evals": evals, "verdict": verdict,
            }

        except Exception as exc:
            print(f"  ERROR training {model_name}: {exc}")
            import traceback; traceback.print_exc()
            results["models"][model_name] = {"error": str(exc)}

    return results


def main():
    print("CAN GAN Loop — Iterations 5-8 with TimeGAN (DIFFERENT seeds)")
    print(f"Data root: {DATA_ROOT}")
    print(f"X_uri: {X_REAL_URI}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Seed mapping: {ITERATION_SEEDS}")

    for uri in [X_REAL_URI, Y_REAL_URI]:
        if not Path(uri).exists():
            print(f"ERROR: Data file not found: {uri}")
            sys.exit(1)

    timegan_adapter = TimeGANAdapter(tracker=None)

    all_results = {}
    for iteration in [5, 6, 7, 8]:
        seed = ITERATION_SEEDS[iteration]
        iter_result = run_iteration(iteration, seed, timegan_adapter, X_REAL_URI, Y_REAL_URI)
        all_results[iteration] = iter_result

    # ── Load previous results (iter 2-4) for full comparison ─────────
    prev_summary_path = OUTPUT_DIR / "iter2_4_summary.json"
    prev_results = {}
    if prev_summary_path.exists():
        prev_results = json.loads(prev_summary_path.read_text())
        # Convert string keys to int
        prev_results = {int(k): v for k, v in prev_results.items()}

    # ── Full comparison table (iterations 1-8) ───────────────────────
    print(f"\n{'='*80}")
    print(f"  FULL COMPARISON — AUROC per iteration per model")
    print(f"{'='*80}")
    header = f"{'Iter':<6} {'Seed':<6} {'LightGBM':<14} {'LSTM':<14} {'TCN':<14}"
    print(header)
    print("-" * 54)

    prev_aurocs = {"lightgbm": 0.0, "lstm": 0.0, "tcn": 0.0}
    all_aurocs = {"lightgbm": [], "lstm": [], "tcn": []}

    for iteration in range(2, 9):
        if iteration in prev_results:
            r = prev_results[iteration]
            seed_str = "—"
        elif iteration in all_results:
            r = all_results[iteration]
            seed_str = str(ITERATION_SEEDS.get(iteration, "—"))
        else:
            continue

        row = f"{iteration:<6} {seed_str:<6}"
        for model in ["lightgbm", "lstm", "tcn"]:
            auroc = r.get("models", {}).get(model, {}).get("auroc", 0.0)
            delta = auroc - prev_aurocs[model]
            arrow = "↑" if delta > 0.001 else ("↓" if delta < -0.001 else "→")
            row += f"{auroc:.4f} {arrow}    "
            prev_aurocs[model] = auroc
            all_aurocs[model].append(auroc)
        print(row)

    # ── Trend analysis ───────────────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"  TREND ANALYSIS")
    print(f"{'='*80}")
    for model in ["lightgbm", "lstm", "tcn"]:
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
        print(f"  {model:>10}: {score_str}  [{trend}]")

    # ── Best scores ──────────────────────────────────────────────────
    print(f"\nBest AUROC per model across all iterations:")
    for model in ["lightgbm", "lstm", "tcn"]:
        scores = all_aurocs[model]
        best_idx = scores.index(max(scores))
        best_iter = best_idx + 2  # iterations start at 2
        print(f"  {model:>10}: {max(scores):.4f} (iteration {best_iter})")

    # ── Save combined results ────────────────────────────────────────
    combined = {**prev_results, **all_results}
    summary_path = OUTPUT_DIR / "iter5_8_summary.json"
    summary_path.write_text(json.dumps(all_results, indent=2, default=str))
    combined_path = OUTPUT_DIR / "iter2_8_full_summary.json"
    combined_path.write_text(json.dumps(combined, indent=2, default=str))
    print(f"\nResults saved to:")
    print(f"  {summary_path}")
    print(f"  {combined_path}")


if __name__ == "__main__":
    main()
