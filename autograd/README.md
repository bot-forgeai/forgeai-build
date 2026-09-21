# autograd

A tiny scalar reverse-mode automatic differentiation engine, plus a
small multi-layer perceptron built on top of it — no numpy, no
tensors, no third-party dependency. Every number in the network is an
individual `Value` node that remembers how it was computed, so calling
`.backward()` on a loss walks the whole computation graph in reverse
and accumulates gradients into every parameter, the same core idea
real frameworks like PyTorch use (just without the vectorization).

This exists to actually *see* backpropagation work, not just call a
library that does it: `autograd/engine.py` is under 150 lines and
implements `+`, `-`, `*`, `/`, `**`, `exp`, `tanh`, `relu`, and
`sigmoid`, each with a matching local backward rule.

## Quick start

```
pip install -e .
autograd-nn train --dataset xor --epochs 300 --lr 0.5 --verbose
```

```
epoch    0  loss=0.2540
epoch   29  loss=0.2318
...
epoch  299  loss=0.0031
final loss: 0.0031
accuracy:   100.0%
```

XOR is the classic "needs a hidden layer" sanity check — no single
linear boundary separates its four points, so a network that solves
it to 100% accuracy is real evidence the gradients are correct, not
just that loss went down a little.

## Datasets

Three tiny synthetic datasets, generated with `random` (seeded, so
runs are reproducible) rather than a downloaded file:

- `xor` — the 4-point XOR problem (not linearly separable).
- `blobs` — two Gaussian clusters (linearly separable, easy).
- `circles` — an inner disk surrounded by a ring (not linearly
  separable, but smoother than XOR's sharp corners).

## CLI

```
autograd-nn train [--dataset xor|blobs|circles] [--hidden N [N ...]]
                   [--epochs N] [--lr F] [--n N] [--seed N] [--verbose]
```

- `--hidden` sets the sizes of the hidden layers, e.g. `--hidden 8 8`
  for two hidden layers of 8 neurons each (default: one layer of 4).
- `--n` controls how many points `blobs`/`circles` generate (ignored
  for `xor`, which is always its fixed 4 points).
- `--verbose` prints the loss roughly every 10% of training.

## Library

```python
from autograd.engine import Value
from autograd.nn import MLP

a = Value(2.0)
b = Value(-3.0)
c = a * b + a ** 2
c.backward()
print(a.grad, b.grad)  # dc/da, dc/db

model = MLP([2, 4, 1], activation="tanh", out_activation="sigmoid", seed=0)
```

## Known limits

- Scalar-only — each number is its own Python object with its own
  Python-level backward closure, so this does not scale past small
  toy networks and datasets. That tradeoff is deliberate: the point
  is transparency (you can print any `Value` and see exactly what
  produced it), not throughput.
- Full-batch gradient descent only (`autograd/train.py`) — no
  mini-batching, no momentum/Adam, no learning-rate schedule.
