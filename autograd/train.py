"""Full-batch training loop for an MLP classifier."""
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


def train(model, xs, ys, epochs=100, lr=0.1, log_every=None, optimizer="sgd"):
    """Trains model in place via full-batch MSE loss and gradient descent.

    `optimizer` selects the update rule ("sgd" or "adam", see optim.py);
    both share the same per-epoch loss/backward computation below and
    differ only in how a parameter's .grad is turned into a .data update.

    Returns a list of the mean-squared-error loss at each epoch, so a
    caller can inspect convergence (or plot it) without re-running.
    """
    if optimizer not in OPTIMIZERS:
        raise ValueError(f"unknown optimizer: {optimizer!r} (choices: {', '.join(OPTIMIZERS)})")
    opt = OPTIMIZERS[optimizer](model.parameters(), lr=lr)

    history = []
    for epoch in range(epochs):
        preds = [predict(model, x) for x in xs]
        losses = [(p - y) ** 2 for p, y in zip(preds, ys)]
        loss = sum(losses) * (1.0 / len(losses))

        model.zero_grad()
        loss.backward()
        opt.step()

        history.append(loss.data)
        if log_every and (epoch % log_every == 0 or epoch == epochs - 1):
            print(f"epoch {epoch:4d}  loss={loss.data:.4f}")

    return history
