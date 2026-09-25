"""Learning-rate schedules: each factory returns an `epoch -> lr` callable,
so `train()` can look up the current epoch's rate without carrying any
schedule-specific state of its own."""
import math

SCHEDULE_NAMES = ("constant", "step", "cosine")


def constant_schedule(base_lr):
    return lambda epoch: base_lr


def step_schedule(base_lr, step_size, decay=0.5):
    """Multiplies lr by `decay` every `step_size` epochs (a staircase)."""
    def f(epoch):
        return base_lr * (decay ** (epoch // step_size))
    return f


def cosine_schedule(base_lr, epochs):
    """Anneals lr from base_lr down to ~0 following a cosine curve over
    the full run, the common "cosine annealing" schedule."""
    denom = max(epochs - 1, 1)

    def f(epoch):
        return base_lr * 0.5 * (1 + math.cos(math.pi * epoch / denom))
    return f


def make_schedule(kind, base_lr, epochs, decay=0.5, step_size=None):
    if kind == "constant":
        return constant_schedule(base_lr)
    if kind == "step":
        if step_size is None:
            step_size = max(1, epochs // 5)
        if step_size < 1:
            raise ValueError(f"lr_step_size must be a positive integer, got {step_size!r}")
        return step_schedule(base_lr, step_size, decay)
    if kind == "cosine":
        return cosine_schedule(base_lr, epochs)
    raise ValueError(f"unknown lr schedule: {kind!r} (choices: {', '.join(SCHEDULE_NAMES)})")
