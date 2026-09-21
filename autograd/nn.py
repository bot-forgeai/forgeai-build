"""A small multi-layer perceptron built entirely on autograd.Value scalars."""
import json
import random

from .engine import Value


class Module:
    def zero_grad(self):
        for p in self.parameters():
            p.grad = 0.0

    def parameters(self):
        return []


class Neuron(Module):
    def __init__(self, nin, activation="tanh", rng=None):
        rng = rng or random
        self.w = [Value(rng.uniform(-1, 1)) for _ in range(nin)]
        self.b = Value(0.0)
        self.activation = activation

    def __call__(self, x):
        act = sum((wi * xi for wi, xi in zip(self.w, x)), self.b)
        if self.activation == "tanh":
            return act.tanh()
        if self.activation == "relu":
            return act.relu()
        if self.activation == "sigmoid":
            return act.sigmoid()
        if self.activation == "linear":
            return act
        raise ValueError(f"unknown activation: {self.activation}")

    def parameters(self):
        return self.w + [self.b]


class Layer(Module):
    def __init__(self, nin, nout, activation="tanh", rng=None):
        self.neurons = [Neuron(nin, activation=activation, rng=rng) for _ in range(nout)]

    def __call__(self, x):
        outs = [n(x) for n in self.neurons]
        return outs[0] if len(outs) == 1 else outs

    def parameters(self):
        return [p for n in self.neurons for p in n.parameters()]


class MLP(Module):
    """A feed-forward network. sizes=[nin, h1, h2, ..., nout].

    Every layer uses `activation` except the last, which uses
    `out_activation` (default "linear", since the loss function usually
    wants raw scores, not a squashed output).
    """

    def __init__(self, sizes, activation="tanh", out_activation="linear", seed=None):
        if len(sizes) < 2:
            raise ValueError("need at least an input and output size")
        self.sizes = list(sizes)
        self.activation = activation
        self.out_activation = out_activation
        rng = random.Random(seed) if seed is not None else random
        self.layers = []
        for i in range(len(sizes) - 1):
            is_last = i == len(sizes) - 2
            act = out_activation if is_last else activation
            self.layers.append(Layer(sizes[i], sizes[i + 1], activation=act, rng=rng))

    def __call__(self, x):
        for layer in self.layers:
            x = layer(x)
        return x

    def parameters(self):
        return [p for layer in self.layers for p in layer.parameters()]

    def to_dict(self):
        """Serializes architecture + current parameter values (not gradients)."""
        return {
            "sizes": self.sizes,
            "activation": self.activation,
            "out_activation": self.out_activation,
            "params": [p.data for p in self.parameters()],
        }

    @classmethod
    def from_dict(cls, d):
        model = cls(d["sizes"], activation=d["activation"], out_activation=d["out_activation"])
        params = model.parameters()
        saved = d["params"]
        if len(saved) != len(params):
            raise ValueError(f"parameter count mismatch: model expects {len(params)}, file has {len(saved)}")
        for p, v in zip(params, saved):
            p.data = v
        return model

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f)

    @classmethod
    def load(cls, path):
        with open(path) as f:
            return cls.from_dict(json.load(f))
