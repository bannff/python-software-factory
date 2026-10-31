---
inclusion: fileMatch
fileMatchPattern: "**/machine_learning/**/adapters/**, **/ml*/**/adapters/**, **/llm_gateway/**/adapters/**"
---
# ML Adapter Guardrails

These rules apply when building or modifying ML adapters (time-series, LLM, etc.). They enforce the **Polymorphic/Agnostic** principle at the model family level.

## The Core Principle

**Native lifecycle family = adapter boundary. Config selects models only when training, serialization, cold loading, and inference authority are genuinely shared.**

The polymorphic boundary is the complete native lifecycle, not superficial use of
the same tensor library. Models may share helpers without sharing ownership.
Native `ncps`, Chronos, and MLX lifecycles remain separate adapters because
their contract inputs, framework serialization, cold loaders, and authority
rules differ.

## The Test

Before creating or merging an adapter, ask:

> *"Does this model share native train, save, fresh-process load, and inference semantics with the existing family?"*

If **yes** → extend the existing adapter's factory dispatch.

If **no** → create or retain a native lifecycle adapter. Never route a family
through generic Torch merely because its implementation can interoperate with
tensors.

## Anti-Patterns (Violations)

### 1. One adapter per model (when native lifecycles are shared)

**Wrong:**
```python
# lstm_timeseries.py
class LstmTimeSeriesAdapter:
    def train(self, ...):
        return train_classifier(model_type, _build_lstm, ...)

# tcn_timeseries.py
class TcnTimeSeriesAdapter:
    def train(self, ...):
        return train_classifier(model_type, _build_tcn, ...)
```

**Right:**
```python
# torch_timeseries.py — one adapter for families sharing the full lifecycle
_MODEL_FACTORIES = {
    TimeSeriesModelType.lstm: _build_lstm,
    TimeSeriesModelType.tcn: _build_tcn,
}

class TorchTimeSeriesAdapter:
    def train(self, model_type, ...):
        build_fn = _MODEL_FACTORIES[model_type]
        return train_classifier(model_type, build_fn, ...)
```

**Why:** LSTM and TCN share native train/save/load semantics; the factory
function is data, not a class. PatchTST and LNN/LTC are intentionally excluded:
PatchTST owns a native Transformers lifecycle, while `ncps.torch.LTC` owns
separate training and live timing contracts with fail-closed validation.

### 2. Model-specific config in adapter signatures

**Wrong:**
```python
class ChronosTimeSeriesAdapter:
    def train(self, ..., lora: bool = True, lora_config: LoRAConfig | None = None):
        # lora is adapter-local, not in port/config
```

**Right:**
```python
@dataclass
class TimeSeriesModelConfig:
    lora: bool = False
    lora_config: LoRAConfig | None = None
    architecture_overrides: dict[str, Any] = field(default_factory=dict)

class TimeSeriesTrainingPort(Protocol):
    def train(self, ..., model_config: TimeSeriesModelConfig | None = None): ...

class ChronosTimeSeriesAdapter:
    def train(self, ..., model_config=None):
        lora = model_config.lora if model_config else False
```

**Why:** Model-specific config belongs in the port, not adapter signatures. Adapter signatures must match the Protocol.

### 3. Model-specific routing via `config.extra`

**Wrong:**
```python
def train(self, ...):
    timespans_uri = cfg.extra.get("timespans_uri")
    if timespans_uri:
        return train_lnn_with_timespans(...)
    return train_classifier(...)
```

**Right:**
```python
@dataclass
class TimeSeriesModelConfig:
    auxiliary_uris: dict[str, str] = field(default_factory=dict)

def train(self, ..., model_config=None):
    if "timespans" in (model_config.auxiliary_uris if model_config else {}):
        return train_lnn_with_timespans(...)
    return train_classifier(...)
```

**Why:** `config.extra` is stringly-typed. Model-specific auxiliary inputs should be explicit in the config, not hidden in a dict bag.

### 4. Shotgun surgery dispatch chains

**Wrong:**
```python
def train(self, model_type, ...):
    if model_type in GENERATIVE_MODELS:
        return self.timegan_adapter.train(...)
    if model_type in TORCH_MODELS:
        return self.torch_adapter.train(...)
    if self._model_registry.has(model_type):
        return self._model_registry.get(model_type).train(...)
```

**Right:**
```python
class ModelAdapterRegistry:
    def dispatch(self, model_type, ...):
        adapter = self._resolve_adapter(model_type)
        return adapter.train(model_type, ...)

def train(self, model_type, ...):
    return self._registry.dispatch(model_type, ...)
```

**Why:** Adding a new model type should not require editing 4 separate methods. The registry encapsulates dispatch logic.

## Correct Patterns

### Family-level adapter with factory dispatch

```python
# torch_timeseries.py
_MODEL_FACTORIES: dict[TimeSeriesModelType, Callable] = {
    TimeSeriesModelType.lstm: lambda inp, cls: LSTMClassifier(input_size=inp, num_classes=cls),
    TimeSeriesModelType.tcn: lambda inp, cls: TCNClassifier(input_size=inp, num_classes=cls),
}

class TorchTimeSeriesAdapter:
    """Shared native lifecycle for LSTM and TCN."""
    def train(self, model_type, X_uri, y_uri, config=None, model_config=None, experiment_name=""):
        build_fn = _MODEL_FACTORIES[model_type]
        grad_clip = model_config.grad_clip if model_config else 1.0
        return train_classifier(model_type, build_fn, X_uri, y_uri, config, "torch_ts_", grad_clip)
```

### Separate adapter for genuinely different training paradigm

```python
# chronos_timeseries.py — foundation model probe, not from-scratch
class ChronosTimeSeriesAdapter:
    """Pretrained foundation model + probe head + optional LoRA."""
    def train(self, model_type, X_uri, y_uri, config=None, model_config=None, experiment_name=""):
        lora = model_config.lora if model_config else False
        # ... chronos-specific pipeline: frozen backbone, embedding extraction, probe head training
```

### Model-specific config flows through port

```python
# ports.py
@dataclass
class TimeSeriesModelConfig:
    """Per-model configuration that flows through the port."""
    grad_clip: float = 1.0
    lora: bool = False
    lora_config: LoRAConfig | None = None
    auxiliary_uris: dict[str, str] = field(default_factory=dict)
    architecture_overrides: dict[str, Any] = field(default_factory=dict)

class TimeSeriesTrainingPort(Protocol):
    def train(
        self,
        model_type: TimeSeriesModelType,
        X_uri: str,
        y_uri: str,
        config: TimeSeriesTrainingConfig | None = None,
        model_config: TimeSeriesModelConfig | None = None,  # <-- NEW
        experiment_name: str = "",
    ) -> TimeSeriesTrainingJob: ...
```

## The Families (Authoritative Target)

| Adapter | Family | Native lifecycle |
|---------|--------|------------------|
| `TorchTimeSeriesAdapter` | Shared Torch sequence | LSTM and TCN |
| `PatchTSTTimeSeriesAdapter` | Transformer sequence | Native Hugging Face/Transformers PatchTST train/save/fresh-process load |
| `NcpsTimeSeriesAdapter` | Liquid neural network | Exact-pinned `ncps.torch.LTC`; prepared training timing for candidate conformance and separate request-scoped live timing for promoted inference; both fail closed |
| `ChronosTimeSeriesAdapter` | Foundation model | Exact-pinned `ChronosPipeline` backbone/revision with framework/PEFT serialization |
| `MlxTimeSeriesAdapter` | MLX sequence | Darwin arm64 only; exact conditional `mlx==0.31.1`; native LSTM/TCN train/save/fresh-process load with frozen identity `mlx/0.31.1/mlx.nn.Module.load_weights/mlx-safetensors/local-mlx-isolated-v1` and an immutable two-file digest tree |
| `SklearnTimeSeriesAdapter` | Tree/gradient | LightGBM native fit/save/cold-load |
| `TimeGANAdapter` | Generative augmentation | Dataset augmentation only; not portfolio inference authority |

## Passport and Conformance Authority

An immutable model passport—not an alias, local path, ranking, warm registry, or
process-local dictionary—is the authority for model family, dataset/feature and
training-timing contracts, exact framework/backbone revision, artifact digest,
adapter descriptor, metrics, and limitations. Cold loaders must validate these
bindings and fail closed on mismatch.

Training timing and production timing are intentionally separate:

- Candidate revision-1 conformance replays the exact prepared training X and
  timing artifacts. Their digest and shape remain immutable promotion evidence.
- Promoted LNN/LTC inference uses `ml_predict_neural_passport` and requires a
  request-scoped `live_timing_uri` plus exact SHA-256 `live_timing_digest`. The
  artifact must be a local, bounded `.npy` containing finite, positive numeric
  values with shape `(len(live X), sealed window_size)`.
- The native loader normalizes live timing with the immutable, training-derived
  `timing_scale`. It does not compare live row count or digest with training
  timing: live shape/digest are execution evidence, not promotion provenance.
- LSTM, TCN, and PatchTST remain timing-omission compatible and reject supplied
  live timing instead of silently ignoring it.
- MLX follows revision-1 candidate → isolated conformance → revision-2
  promotion. `ml_predict_timeseries` is not durable MLX authority; production
  accepts only the exact promoted revision-2 reference through
  `ml_predict_neural_passport`.

The MLX trust root is `ML_MODEL_PASSPORT_ROOT`, not a family-specific override.

The deployable the control-plane runtime environment and the machine-learning brick both
exact-pin `ncps==1.0.1`; the passport also seals and verifies that framework
version before native LTC execution.

### Durable CAN lifecycle

The five workflow-facing CAN lifecycle tools are attempt-idempotent:
`attempt_id` binds to the canonical semantic request and versioned tool
identities. Equal retries replay the stored terminal; divergent reuse returns
`conflict`. Effects use deterministic identities. After a native LNN or Chronos
job and its immutable replay record are published, a retry can authenticate that
record and reconcile an interruption before the lifecycle effect receipt was
stored. This does not claim recovery for a crash before the replay record exists.

`ml_train_can_portfolio` accepts a Dataset request and consumes the completed
terminal's exact family refs: LightGBM (the backward-compatible default) uses
`contract`/`x_2d`/`y`; Chronos uses `contract`/`x_3d`/`y` plus a caller-supplied
sealed local `model_config.local_backbone_ref`; LNN uses
`contract`/`x_3d`/`y`/`timespans`, and derives its model config from that exact
timing ref rather than accepting caller timing, backbone, or LoRA overrides.
LNN model bytes use the dedicated `ML_LNN_MODEL_ROOT` beneath passport
authority; Chronos validates its sealed backbone and model roots beneath that
same authority. Dataset, Evals, passport, conformance, and promotion authority
remain at their owning MCP boundaries; downstream calls pass exact terminal,
passport, and receipt refs rather than trusted result bodies.

The `python-factory-sbhyq.12.1` acceptance gate starts two different API PIDs
against the same durable roots, discovers Dataset and ML over localhost
Streamable HTTP `/mcp/`, verifies an empty warm registry after restart, and
cold-scores exact revision-2 LNN and Chronos passports. It also rejects tampered
LNN model/timing, Chronos backbone, and passport bytes while proving the server
remains available. Offline mode prevents external uv/Hugging Face acquisition;
localhost MCP traffic is required.

`python-factory-sbhyq.8.5` is the one portfolio-wide native
train/cold-load/restart/parity/tamper/authority matrix for LightGBM, LSTM, TCN,
PatchTST, LNN/LTC, Chronos, and supported MLX. It includes exact
framework/backbone pins and adapter descriptor checks. `.8.6` is closed as
superseded and must not be recreated as a parallel gate.

## Canary Tests

When building a family-level adapter, add a canary test that pins the factory dispatch:

```python
def test_canary_model_factory_dispatch():
    """Pin shared Torch dispatch without absorbing native families."""
    from factory.machine_learning.runtime.adapters.torch_timeseries import _MODEL_FACTORIES
    assert TimeSeriesModelType.lstm in _MODEL_FACTORIES
    assert TimeSeriesModelType.tcn in _MODEL_FACTORIES
    assert TimeSeriesModelType.patchtst not in _MODEL_FACTORIES
    assert TimeSeriesModelType.lnn not in _MODEL_FACTORIES
```

This fails fast if shared dispatch drifts or PatchTST/LNN-LTC are routed back
through generic Torch instead of their native Transformers/`ncps` lifecycles.

## References

- **Principle:** `.agents/steering/dev-principles.md` §Polymorphic/Agnostic
- **Epic:** bd `python-factory-sq4` (ML adapter polymorphic refactor)
- **Sub-issues:** `python-factory-lld` (boilerplate), `python-factory-789` (lora hardcode), `python-factory-650` (timespans leak), `python-factory-qsy` (dispatch chains)
- **Existing exemplar:** `TorchTimeSeriesAdapter` handles LSTM + TCN via `build_model()` dispatch
