"""Observable contracts for the portable tiny audio demo."""

from __future__ import annotations

import importlib.util
import io
import json
import wave
from pathlib import Path

import numpy as np
import pytest
import torch


DEMO = Path(__file__).parents[1] / "experiments/edge_models/edge-audio-device-demo-001"
SOURCE = Path(__file__).parents[1] / "experiments/edge_models/edge-audio-command-001/run.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wav_bytes(samples: np.ndarray, rate: int = 16000) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(samples.astype("<i2").tobytes())
    return output.getvalue()


def test_preprocessing_matches_training_and_rejects_unexpected_audio() -> None:
    runtime = load_module(DEMO / "runtime.py", "audio_runtime_features")
    source = load_module(SOURCE, "audio_source_features")
    x = (np.sin(np.arange(16000) * 2 * np.pi * 220 / 16000) * 12000).astype(np.int16)
    raw = wav_bytes(x)
    np.testing.assert_allclose(runtime.log_mel(raw), source.features(raw, source.mel_filters()), atol=2e-4)
    with pytest.raises(ValueError, match="WAV"):
        runtime.log_mel(wav_bytes(np.zeros(16001, dtype=np.int16)))
    with pytest.raises(ValueError, match="WAV"):
        runtime.log_mel(wav_bytes(np.zeros(400, dtype=np.int16), rate=8000))


def test_numpy_export_matches_pytorch_probabilities(tmp_path: Path) -> None:
    runtime = load_module(DEMO / "runtime.py", "audio_runtime_model")
    prepare = load_module(DEMO / "prepare.py", "audio_prepare_model")
    source = load_module(SOURCE, "audio_source_model")
    torch.manual_seed(14)
    model = source.TinyDSCNN().eval()
    artifact = tmp_path / "model.npz"
    prepare.write_numpy_model(model.state_dict(), mean=-14.0, std=3.0, output=artifact)
    portable = runtime.load_model(artifact)
    samples = (np.sin(np.arange(16000) * 2 * np.pi * 440 / 16000) * 11000).astype(np.int16)
    raw = wav_bytes(samples)
    feature = source.features(raw, source.mel_filters())
    with torch.no_grad():
        logits = model(torch.from_numpy(((feature + 14.0) / 3.0)[None, None])).numpy()[0]
    reference = np.exp(logits - logits.max())
    reference /= reference.sum()
    actual = runtime.predict(portable, raw)["probabilities"]
    np.testing.assert_allclose(actual, reference, atol=2e-4, rtol=2e-4)


def test_cohort_selection_is_test_only_and_speaker_unique() -> None:
    prepare = load_module(DEMO / "prepare.py", "audio_prepare_cohort")
    rows = [
        {"filename": f"mini_speech_commands/{word}/{speaker}_nohash_0.wav", "word": word,
         "speaker": speaker, "split": "test"}
        for word, speaker in (("go", "a"), ("go", "b"), ("stop", "c"), ("stop", "d"),
                              ("no", "e"), ("left", "f"))
    ]
    rows.append({"filename": "mini_speech_commands/go/z_nohash_0.wav", "word": "go",
                 "speaker": "z", "split": "train"})
    selected = prepare.select_cohort(rows, per_class=2)
    assert len(selected) == 6
    assert {row["split"] for row in selected} == {"test"}
    assert len({row["speaker"] for row in selected}) == 6
    assert {prepare.class_for_word(row["word"]) for row in selected} == {"go", "stop", "other"}


def test_runtime_rejects_non_anonymous_clip_identity(tmp_path: Path) -> None:
    runtime = load_module(DEMO / "runtime.py", "audio_runtime_boundary")
    prepare = load_module(DEMO / "prepare.py", "audio_prepare_boundary")
    source = load_module(SOURCE, "audio_source_boundary")
    model = tmp_path / "model.npz"
    prepare.write_numpy_model(source.TinyDSCNN().state_dict(), mean=-14.0, std=3.0, output=model)
    cohort = tmp_path / "cohort.json"
    cohort.write_text(json.dumps({"clips": [{"clip_id": "clip-001/..", "filename": "clip-001.wav",
                                            "sha256": "0" * 64}]}))
    with pytest.raises(ValueError, match="Invalid clip identity"):
        runtime.run(model, cohort, tmp_path / "predictions.json", repeats=1)


def test_demo_output_exposes_audio_and_predictions_without_source_names(tmp_path: Path) -> None:
    render = load_module(DEMO / "render.py", "audio_demo_render")
    clips = tmp_path / "clips"
    clips.mkdir()
    (clips / "clip-001.wav").write_bytes(wav_bytes(np.zeros(400, dtype=np.int16)))
    predictions = {"predictions": [{"clip_id": "clip-001", "prediction": "go",
                                    "probabilities": [0.8, 0.1, 0.1], "latency_ms": 1.0}]}
    truth = {"clips": [{"clip_id": "clip-001", "word": "go", "label": "go",
                         "source_filename": "private_name_nohash_0.wav"}]}
    output = tmp_path / "demo.html"
    render.write_demo(predictions, truth, clips, output)
    text = output.read_text()
    assert "audio controls" in text
    assert "data:audio/wav;base64," in text
    assert "go" in text
    assert "private_name" not in text


def test_payload_staging_rejects_host_labels_and_extra_files(tmp_path: Path) -> None:
    layout = load_module(DEMO / "payload_layout.py", "audio_payload_layout")
    payload = tmp_path / "payload"
    clips = payload / "clips"
    clips.mkdir(parents=True)
    raw = wav_bytes(np.zeros(400, dtype=np.int16))
    (payload / "model.npz").write_bytes(b"model")
    (clips / "clip-001.wav").write_bytes(raw)
    import hashlib
    (payload / "cohort.json").write_text(json.dumps({"schema_version": 1, "clips": [
        {"clip_id": "clip-001", "filename": "clip-001.wav", "sha256": hashlib.sha256(raw).hexdigest()}
    ]}))
    layout.validate_payload(payload)

    (payload / "truth.json").write_text('{"label":"go"}')
    with pytest.raises(ValueError, match="extra files"):
        layout.validate_payload(payload)
    (payload / "truth.json").unlink()

    cohort = json.loads((payload / "cohort.json").read_text())
    cohort["clips"][0]["label"] = "go"
    (payload / "cohort.json").write_text(json.dumps(cohort))
    with pytest.raises(ValueError, match="label-free"):
        layout.validate_payload(payload)


def test_prepare_requires_fresh_output_directory(tmp_path: Path) -> None:
    prepare = load_module(DEMO / "prepare.py", "audio_prepare_fresh_output")
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(ValueError, match="new directory"):
        prepare.prepare(tmp_path / "archive.zip", tmp_path / "split.tsv",
                        tmp_path / "checkpoint.pt", output)
