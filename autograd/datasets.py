"""Small synthetic datasets for exercising the MLP, generated with no
external dependency (stdlib random only) so the whole project stays
offline and dependency-free.
"""
import math
import random


def make_xor():
    """The classic 4-point XOR problem. Not linearly separable, so it
    requires a hidden layer -- a good sanity check that backprop works.
    """
    xs = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
    ys = [0.0, 1.0, 1.0, 0.0]
    return xs, ys


def make_blobs(n=60, seed=0):
    """Two Gaussian blobs centered at (-1.5, -1.5) and (1.5, 1.5),
    labeled 0 and 1 -- a linearly separable sanity check.
    """
    rng = random.Random(seed)
    xs, ys = [], []
    centers = [(-1.5, -1.5, 0.0), (1.5, 1.5, 1.0)]
    for _ in range(n):
        cx, cy, label = centers[rng.randint(0, 1)]
        xs.append([cx + rng.gauss(0, 0.5), cy + rng.gauss(0, 0.5)])
        ys.append(label)
    return xs, ys


def make_circles(n=80, seed=0):
    """An inner circle (label 0) surrounded by an outer ring (label 1)
    -- not linearly separable, harder than blobs but easier than XOR's
    sharp corners.
    """
    rng = random.Random(seed)
    xs, ys = [], []
    for i in range(n):
        label = i % 2
        radius = 0.5 if label == 0 else 2.0
        angle = rng.uniform(0, 2 * math.pi)
        r = radius + rng.gauss(0, 0.15)
        xs.append([r * math.cos(angle), r * math.sin(angle)])
        ys.append(float(label))
    return xs, ys


DATASETS = {
    "xor": lambda **kw: make_xor(),
    "blobs": make_blobs,
    "circles": make_circles,
}
