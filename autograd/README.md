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
                   [--epochs N] [--lr F] [--optimizer sgd|adam]
                   [--batch-size N] [--n N] [--seed N] [--verbose]
```

- `--hidden` sets the sizes of the hidden layers, e.g. `--hidden 8 8`
  for two hidden layers of 8 neurons each (default: one layer of 4).
- `--optimizer` picks the update rule (default: `sgd`, plain gradient
  descent). `adam` (`autograd/optim.py`) tracks per-parameter running
  estimates of the gradient's first and second moments and typically
  converges much faster on harder problems like `xor` — but wants a
  smaller `--lr` than `sgd` does; try `--lr 0.05` as a starting point.
- `--batch-size N` splits each epoch into shuffled batches of `N`
  examples, taking one optimizer step per batch instead of one step
  over the whole dataset (default: full-batch, unchanged). Reported
  per-epoch loss is the mean of that epoch's per-batch losses.
- `--lr-schedule {constant,step,cosine}` (`autograd/lr_schedule.py`)
  changes `--lr` over the run instead of holding it fixed (default:
  `constant`, unchanged behavior): `step` multiplies it by
  `--lr-decay` (default 0.5) every `--lr-step-size` epochs (default
  `epochs // 5`); `cosine` anneals it from `--lr` down to ~0 following
  a cosine curve over the whole run. `--verbose` prints the current
  `lr` alongside `loss` each logged epoch.
- `--n` controls how many points `blobs`/`circles` generate (ignored
  for `xor`, which is always its fixed 4 points).
- `--verbose` prints the loss roughly every 10% of training.
- `--save PATH` saves the trained model (architecture + weights, as
  JSON) after training finishes.
- `autograd-nn --version` prints the installed package version and exits.

```
autograd-nn predict MODEL_PATH X [X ...]
```

Loads a model saved via `train --save` and runs one forward pass on
the given input values, printing the raw output. Errors cleanly (exit
1) on a missing/malformed file or an input count that doesn't match
the model's expected number of inputs.

```
autograd-nn train --dataset xor --epochs 300 --lr 0.5 --save xor.json
autograd-nn predict xor.json 1 0
# 0.8724
```

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

model.save("model.json")
loaded = MLP.load("model.json")  # architecture + weights, ready to use
```

## Known limits

- Scalar-only — each number is its own Python object with its own
  Python-level backward closure, so this does not scale past small
  toy networks and datasets. That tradeoff is deliberate: the point
  is transparency (you can print any `Value` and see exactly what
  produced it), not throughput.
- `autograd/optim.py` provides both plain SGD and Adam, selectable via
  `--optimizer`; `autograd/train.py` supports mini-batching via
  `--batch-size` alongside the default full-batch mode, and a
  learning-rate schedule via `--lr-schedule` (constant, step, or
  cosine) instead of a rate fixed for the whole run.
