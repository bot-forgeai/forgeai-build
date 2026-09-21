"""Full-batch gradient descent training loop for an MLP classifier."""
from .engine import Value


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


def train(model, xs, ys, epochs=100, lr=0.1, log_every=None):
    """Trains model in place via full-batch MSE gradient descent.

    Returns a list of the mean-squared-error loss at each epoch, so a
    caller can inspect convergence (or plot it) without re-running.
    """
    history = []
    for epoch in range(epochs):
        preds = [predict(model, x) for x in xs]
        losses = [(p - y) ** 2 for p, y in zip(preds, ys)]
        loss = sum(losses) * (1.0 / len(losses))

        model.zero_grad()
        loss.backward()
        for p in model.parameters():
            p.data -= lr * p.grad

        history.append(loss.data)
        if log_every and (epoch % log_every == 0 or epoch == epochs - 1):
            print(f"epoch {epoch:4d}  loss={loss.data:.4f}")

    return history
