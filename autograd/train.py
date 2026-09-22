"""Full-batch or mini-batch training loop for an MLP classifier."""
import random

from .engine import Value
from .optim import OPTIMIZERS


def predict(model, x):
    out = model([Value(v) for v in x])
    return out if isinstance(out, Value) else out[0]


def accuracy(model, xs, ys, threshold=0.5):
    correct = 0
    for x, y in zip(xs, ys):
        pred = predict(model, x).data
        label = 1.0 if pred >= threshold else 0.0
        if label == y:
            correct += 1
    return correct / len(xs)


def _iter_batches(xs, ys, batch_size, rng):
    n = len(xs)
    order = list(range(n))
    if rng is not None:
        rng.shuffle(order)
    if batch_size is None:
        batch_size = n
    for start in range(0, n, batch_size):
        idx = order[start:start + batch_size]
        yield [xs[i] for i in idx], [ys[i] for i in idx]


def train(model, xs, ys, epochs=100, lr=0.1, log_every=None, optimizer="sgd",
          batch_size=None, shuffle=True, seed=None):
    """Trains model in place via MSE loss and gradient descent.

    `optimizer` selects the update rule ("sgd" or "adam", see optim.py);
    both share the same per-batch loss/backward computation below and
    differ only in how a parameter's .grad is turned into a .data update.

    `batch_size` controls how many examples contribute to each gradient
    step: `None` (the default) reproduces the original full-batch
    behavior (one step per epoch, over every example); any positive int
    splits each epoch into batches of that size instead, taking one
    optimizer step per batch. `shuffle` (default True) reshuffles example
    order at the start of every epoch when batching, so successive
    batches aren't always the same fixed groups; it's a no-op in
    full-batch mode since batch order doesn't affect a single-step
    epoch. `seed` makes shuffling deterministic for tests.

    Returns a list of the mean-squared-error loss at each epoch (the
    mean over that epoch's per-batch losses in mini-batch mode), so a
    caller can inspect convergence (or plot it) without re-running.
    """
    if optimizer not in OPTIMIZERS:
        raise ValueError(f"unknown optimizer: {optimizer!r} (choices: {', '.join(OPTIMIZERS)})")
    if batch_size is not None and batch_size < 1:
        raise ValueError(f"batch_size must be a positive integer, got {batch_size!r}")
    opt = OPTIMIZERS[optimizer](model.parameters(), lr=lr)
    rng = random.Random(seed) if shuffle and batch_size is not None else None

    history = []
    for epoch in range(epochs):
        epoch_losses = []
        for batch_xs, batch_ys in _iter_batches(xs, ys, batch_size, rng):
            preds = [predict(model, x) for x in batch_xs]
            losses = [(p - y) ** 2 for p, y in zip(preds, batch_ys)]
            loss = sum(losses) * (1.0 / len(losses))

            model.zero_grad()
            loss.backward()
            opt.step()

            epoch_losses.append(loss.data)

        epoch_loss = sum(epoch_losses) / len(epoch_losses)
        history.append(epoch_loss)
        if log_every and (epoch % log_every == 0 or epoch == epochs - 1):
            print(f"epoch {epoch:4d}  loss={epoch_loss:.4f}")

    return history
