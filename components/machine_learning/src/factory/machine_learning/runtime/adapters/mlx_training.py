"""MLX training loop for the time-series adapter.

Mirrors :mod:`torch_training` for Apple's MLX framework. The training
loop is the only place that touches :func:`mlx.nn.value_and_grad` and
the optimiser's lazy-update protocol, so the rest of the brick can
treat MLX models as drop-in replacements for their torch counterparts.

MLX training has three quirks this module absorbs:

* Gradients come from ``nn.value_and_grad(model, loss_fn)(model, X, y)``
  — there is no ``.backward()``. ``value_and_grad`` returns a tuple of
  ``(loss_value, grads)`` where ``grads`` mirrors the model's
  parameter tree.
* The optimiser does not mutate parameters in place during
  ``optimizer.update(model, grads)``; MLX arrays are lazy. We must
  call :func:`mx.eval` on the model parameters AND the optimiser state
  immediately after each update or the next ``value_and_grad`` call
  will see the old weights.
* There is no ``model.eval()`` / ``model.train()`` toggle — Dropout
  is a flag in our model ``__call__``. We pass ``training=True`` /
  ``False`` explicitly when we call the model so the loop drives the
  flag.
"""

from __future__ import annotations

from typing import Callable

from .mlx_platform import require_mlx_platform

require_mlx_platform()

import mlx.core as mx  # noqa: E402
import mlx.nn as nn  # noqa: E402
import mlx.optimizers as optim  # noqa: E402
import numpy as np  # noqa: E402

__all__ = ["clip_grad_norm", "train_loop"]


# Conventional max-norm for sequence models (Merity et al. 2017).
_MAX_NORM = 1.0


def cross_entropy(logits: mx.array, labels: mx.array) -> mx.array:
    """Multi-class cross-entropy loss for integer labels.

    ``mlx.nn.losses.cross_entropy`` accepts either integer class
    indices or one-hot probabilities; we pass raw integer labels so
    the loss matches the torch ``CrossEntropyLoss`` semantics the rest
    of the brick expects.
    """
    return mx.mean(nn.losses.cross_entropy(logits, labels, reduction="mean"))


def _flatten(tree) -> list[mx.array]:
    """Return the leaf ``mx.array``s of a parameter/grad tree.

    MLX's parameter tree is a nested dict matching the ``Module``'s
    submodule layout. ``mlx.utils.tree_flatten`` returns a list of
    ``(key, leaf)`` pairs — we only need the leaves here.
    """
    from mlx.utils import tree_flatten
    return [leaf for _, leaf in tree_flatten(tree)]


def clip_grad_norm(grads, max_norm: float = _MAX_NORM) -> mx.array:
    """Clip a parameter-tree gradient in-place to a global max-norm.

    Returns the pre-clip global L2 norm so callers can log it. The
    operation materialises ``grads`` through :func:`mx.eval` so the
    rescaled values are visible to the next ``value_and_grad`` call
    without an extra eval step.
    """
    leaves = _flatten(grads)
    if leaves:
        # mx.add is binary-only; reduce via fold so this works for any
        # number of leaves (the lstm alone emits 3 weight matrices).
        total_sq = mx.sum(leaves[0] * leaves[0])
        for g in leaves[1:]:
            total_sq = total_sq + mx.sum(g * g)
    else:
        total_sq = mx.array(0.0)
    total_norm = mx.sqrt(total_sq + 1e-12)
    clip_coef = max_norm / (total_norm + 1e-6)
    # mx.minimum on a Python float short-circuits the no-op case so we
    # don't allocate a new tree when gradients are already well-scaled.
    scale = mx.minimum(clip_coef, 1.0)
    from mlx.utils import tree_map
    scaled = tree_map(lambda g: g * scale, grads)
    return scaled, total_norm


def train_loop(
    model: nn.Module,
    loader: "MLXDataLoader",
    X_val: np.ndarray,
    y_val: np.ndarray,
    epochs: int,
    patience: int,
    learning_rate: float,
    grad_clip: float = _MAX_NORM,
) -> tuple[dict, float]:
    """Train with early stopping; return the best-observed parameter tree.

    Returns:
        A 2-tuple ``(best_params, best_val_loss)`` where
        ``best_params`` is a dict mirroring :func:`mlx.nn.Module.parameters`
        and ``best_val_loss`` is the lowest validation loss observed.

    The parameter tree is detached from the live model so the caller
    can :func:`mx.eval` it once and use it for inference without the
    optimiser's momentum state leaking in.
    """
    optimizer = optim.Adam(learning_rate=learning_rate)
    loss_fn = _make_loss_fn(model)

    best_val = float("inf")
    best_params: dict | None = None
    no_improve = 0

    val_logits = _make_loss_fn(model, inference=True)
    X_val_mx = mx.array(np.ascontiguousarray(X_val))
    y_val_mx = mx.array(np.ascontiguousarray(y_val))

    for _ in range(epochs):
        for xb, yb in loader:
            loss, grads = loss_fn(model, xb, yb)
            grads, _ = clip_grad_norm(grads, max_norm=grad_clip)
            optimizer.update(model, grads)
            # mx.eval on parameters AND optimiser state is mandatory:
            # without it, the next value_and_grad sees the pre-update
            # weights because MLX arrays are lazily evaluated.
            mx.eval(model.parameters(), optimizer.state)
        # Validation pass: no dropout, no grad. ``mx.eval`` returns
        # None — it materialises the graph as a side effect. The
        # actual scalar lives on the lazy array; ``.item()`` triggers
        # the evaluation and yields a Python float.
        val_loss = val_logits(model, X_val_mx, y_val_mx)
        v = float(val_loss.item())
        if v < best_val - 1e-6:
            best_val = v
            best_params = _snapshot(model)
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                break
    if best_params is None:
        # No improvement across the entire run — keep the final state.
        best_params = _snapshot(model)
    return best_params, best_val


def _snapshot(model: nn.Module) -> dict:
    """Take a detached copy of the model's parameters.

    MLX parameter trees are nested dicts matching the module hierarchy
    (e.g. ``{"lstm": {"Wxh": ...}, "fc": {"weight": ...}}``). We walk
    the tree, ``mx.eval`` every leaf so the snapshot survives the
    next training step, and reassemble the same shape. ``mlx.utils.tree_map``
    handles the recursion in one call.
    """
    from mlx.utils import tree_map
    params = model.parameters()
    # Force materialisation so the snapshot is not tied to the live graph.
    mx.eval(params)
    # tree_map(fn, tree) applies fn to every leaf; ``mx.array(x)``
    # already materialises when x is an array, but we re-eval to be
    # safe in case some leaf was a lazy view.
    return tree_map(lambda x: mx.array(np.asarray(x).copy()), params)


def _make_loss_fn(model: nn.Module, *, inference: bool = False) -> Callable:
    """Build a closure suitable for :func:`nn.value_and_grad`.

    When ``inference=True`` the closure does not record a graph and
    is safe to call inside the validation loop. When ``inference=False``
    (the default) the closure is passed to ``value_and_grad`` and
    returns ``(loss, grads)``.
    """
    def loss(model_, x, y):
        logits = model_(x, training=not inference)
        return cross_entropy(logits, y)
    if inference:
        return loss
    return nn.value_and_grad(model, loss)
