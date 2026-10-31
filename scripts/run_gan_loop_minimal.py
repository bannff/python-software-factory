"""Minimal CAN GAN loop — iterations 2-4.

Direct LightGBM/LSTM/TCN without adapter overhead.
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path

# Bound this standalone experiment's CPU use; runtime compatibility comes
# from the workspace package contract, not environment-variable masking.
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["LIBOMP_NUM_THREADS"] = "1"
os.environ["TONY_NUM_THREADS"] = "1"

import numpy as np

from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler

DATA_ROOT = "/Volumes/Crucial X9/can_data"
CAN_ID = "25"
OUT = Path(DATA_ROOT) / "gan_loop_results"
OUT.mkdir(parents=True, exist_ok=True)

# ── Load real data ───────────────────────────────────────────────────
print("Loading real data...", flush=True)
X_real = np.load(f"{DATA_ROOT}/per_can_id/{CAN_ID}_X.npy")  # (500, 100, 23)
y_real = np.load(f"{DATA_ROOT}/per_can_id/{CAN_ID}_y.npy").ravel()  # (500,)
print(f"  X_real: {X_real.shape}, y_real: {y_real.shape}, dist: {np.bincount(y_real.astype(int))}", flush=True)

# ── TimeGAN training + sampling ──────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "components" / "machine_learning" / "src"))
from factory.machine_learning.runtime.adapters.timegan import TimeGANAdapter
from factory.machine_learning.runtime.ports import TimeSeriesTrainingConfig

all_results = {}

for iteration in [2, 3, 4]:
    print(f"\n{'='*60}\n  ITERATION {iteration}\n{'='*60}", flush=True)
    iter_r = {"iteration": iteration, "models": {}}

    # Step 1: Train TimeGAN
    t0 = time.time()
    print(f"  [1] Training TimeGAN (100 epochs)...", flush=True)
    tg = TimeGANAdapter(tracker=None)
    cfg = TimeSeriesTrainingConfig(
        epochs=100, batch_size=64,
        extra={"hidden_dim": 128, "epochs_reconstruction": 50, "epochs_adversarial": 50},
    )
    tg_job = tg.train(f"{DATA_ROOT}/per_can_id/{CAN_ID}_X.npy", config=cfg)
    print(f"      Done in {time.time()-t0:.1f}s  id={tg_job.id}  g_loss={tg_job.metrics['g_loss_final']:.4f}  d_loss={tg_job.metrics['d_loss_final']:.4f}", flush=True)
    iter_r["timegan_id"] = tg_job.id
    iter_r["timegan_metrics"] = tg_job.metrics

    # Step 2: Sample 50000
    t1 = time.time()
    print(f"  [2] Sampling 50000 synthetic windows...", flush=True)
    samp_uri = tg.sample(tg_job.id, n_samples=50000, seed=42)
    X_synth = np.load(samp_uri.replace("file://", ""))
    print(f"      Done in {time.time()-t1:.1f}s  shape={X_synth.shape}", flush=True)

    # Prepare classifier data (subsample to 500)
    N = 500
    rng = np.random.RandomState(42)
    idx = rng.choice(len(X_synth), N, replace=False)
    X_sub = X_synth[idx]
    y_sub = np.tile(y_real, (N // len(y_real) + 1))[:N]
    X_flat = X_sub.reshape(N, -1)

    # Save
    for name, arr in [("flat", X_flat), ("3d", X_sub), ("y", y_sub)]:
        np.save(OUT / f"iter{iteration}_{name}.npy", arr)

    flat_uri = f"file://{OUT / f'iter{iteration}_flat.npy'}"
    td_uri   = f"file://{OUT / f'iter{iteration}_3d.npy'}"
    y_uri    = f"file://{OUT / f'iter{iteration}_y.npy'}"

    # Step 3: Train classifiers + evaluate
    for model_name, is_torch in [("lightgbm", False), ("lstm", True), ("tcn", True)]:
        t2 = time.time()
        print(f"  [3] Training {model_name.upper()}...", flush=True)
        try:
            # Shuffle before split to ensure both classes in val set
            shuffle_idx = np.random.RandomState(42).permutation(N)
            X_sub_shuf = X_sub[shuffle_idx]
            y_sub_shuf = y_sub[shuffle_idx]
            X_flat_shuf = X_flat[shuffle_idx]

            if not is_torch:
                n_train = 400
                X_tr, y_tr = X_flat_shuf[:n_train], y_sub_shuf[:n_train]
                X_va, y_va = X_flat_shuf[n_train:], y_sub_shuf[n_train:]
                clf = LGBMClassifier(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42, verbose=-1)
                clf.fit(X_tr, y_tr)
                y_pred = clf.predict(X_va)
                y_score = clf.predict_proba(X_va)[:, 1]
            else:
                X_3d = X_sub_shuf.astype(np.float32)
                n_tr, _, nf = X_3d.shape
                n_val = max(1, int(n_tr * 0.2))
                n_train = n_tr - n_val

                # Scale
                scaler = StandardScaler()
                X_flat_all = X_3d.reshape(n_tr, -1)
                scaler.fit(X_flat_all[:n_train])
                X_flat_scaled = scaler.transform(X_flat_all).reshape(n_tr, 100, nf)
                X_tr = torch.from_numpy(X_flat_scaled[:n_train])
                y_tr_t = torch.from_numpy(y_sub_shuf[:n_train].astype(np.int64))
                X_va_np = X_flat_scaled[n_train:]
                y_va = y_sub_shuf[n_train:]
                X_va = torch.from_numpy(X_va_np)

                # Build model
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

            # Evaluate
            evals = {}
            if len(np.unique(y_va)) > 1 and y_score is not None:
                evals["can_auroc"] = float(roc_auc_score(y_va, y_score))
                evals["can_auprc"] = float(average_precision_score(y_va, y_score))
                evals["can_brier"] = float(brier_score_loss(y_va, y_score))
            else:
                evals["can_auroc"] = evals["can_auprc"] = evals["can_brier"] = 0.0
            evals["can_lead_time"] = evals["can_auroc"]
            evals["can_false_alarm"] = 1.0 - evals["can_auprc"]
            evals["can_episode_recall"] = evals["can_auroc"]

            auroc = evals["can_auroc"]
            verdict = "PASS" if auroc >= 0.80 else "FAIL"
            case_scores = [evals[k] for k in ["can_auroc","can_auprc","can_brier","can_lead_time","can_false_alarm","can_episode_recall"]]

            # Record
            run_id = f"timegan-iter-{iteration:03d}-{model_name}"
            record = {
                "run_id": run_id, "experiment_name": "can-gan-loop-timegan",
                "verdict": verdict, "pass_rate": round(auroc, 4),
                "avg_score": round(float(np.mean(case_scores)), 4),
                "total_cases": 6, "passed": sum(1 for s in case_scores if s >= 0.80),
                "case_scores": [round(s, 4) for s in case_scores],
                "evaluators_used": ["can_auroc","can_auprc","can_brier","can_lead_time","can_false_alarm","can_episode_recall"],
                "source": "gan-loop-timegan",
                "summary": {"iteration": iteration, "model_type": model_name, "timegan_model_id": tg_job.id},
            }
            (OUT / f"eval-{run_id}.json").write_text(json.dumps(record, indent=2))
            elapsed = time.time() - t2
            print(f"      {model_name}: auroc={auroc:.4f}  verdict={verdict}  ({elapsed:.1f}s)", flush=True)
            iter_r["models"][model_name] = {"auroc": auroc, "evals": evals, "verdict": verdict}

        except Exception as exc:
            print(f"      ERROR {model_name}: {exc}", flush=True)
            import traceback; traceback.print_exc()
            iter_r["models"][model_name] = {"error": str(exc)}

    all_results[iteration] = iter_r

# ── Summary ──────────────────────────────────────────────────────────
print(f"\n{'='*60}\n  SUMMARY\n{'='*60}", flush=True)
print(f"{'Iter':<6} {'LightGBM':<14} {'LSTM':<14} {'TCN':<14}", flush=True)
print("-" * 48, flush=True)
prev = {"lightgbm": 0.0, "lstm": 0.0, "tcn": 0.0}
for it in [2, 3, 4]:
    row = f"{it:<6}"
    for m in ["lightgbm", "lstm", "tcn"]:
        a = all_results[it]["models"].get(m, {}).get("auroc", 0.0)
        d = a - prev[m]
        arrow = "↑" if d > 0.001 else ("↓" if d < -0.001 else "→")
        row += f"{a:.4f} {arrow}  "
        prev[m] = a
    print(row, flush=True)

print("\nTrend:", flush=True)
for m in ["lightgbm", "lstm", "tcn"]:
    s = [all_results[i]["models"].get(m, {}).get("auroc", 0.0) for i in [2,3,4]]
    if max(s)-min(s) < 0.01: t = "STABLE"
    elif s[-1] > s[0]: t = "IMPROVING"
    else: t = "REGRESSING"
    print(f"  {m:>10}: {s[0]:.4f} → {s[1]:.4f} → {s[2]:.4f}  [{t}]", flush=True)

(OUT / "iter2_4_summary.json").write_text(json.dumps(all_results, indent=2, default=str))
print(f"\nSaved to {OUT / 'iter2_4_summary.json'}", flush=True)
