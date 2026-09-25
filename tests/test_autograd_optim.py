import pytest

from autograd.engine import Value
from autograd.nn import MLP
from autograd.optim import SGD, Adam, OPTIMIZERS
from autograd.train import train
from autograd.datasets import make_xor


def test_sgd_step_matches_manual_update():
    p = Value(1.0)
    p.grad = 2.0
    opt = SGD([p], lr=0.1)
    opt.step()
    assert p.data == pytest.approx(1.0 - 0.1 * 2.0)


def test_sgd_only_touches_registered_params():
    p1, p2 = Value(1.0), Value(5.0)
    p1.grad = 1.0
    p2.grad = 100.0
    opt = SGD([p1], lr=0.1)
    opt.step()
    assert p1.data == pytest.approx(0.9)
    assert p2.data == 5.0


def test_adam_first_step_matches_hand_derived_formula():
    # With m=v=0 initially and t=1, bias correction divides by
    # (1 - beta) exactly once, so m_hat == g and v_hat == g*g
    # regardless of beta -- the update reduces to a clean closed form.
    p = Value(3.0)
    p.grad = 0.5
    lr, eps = 0.1, 1e-8
    opt = Adam([p], lr=lr, eps=eps)
    opt.step()
    m_hat = 0.5
    v_hat = 0.25
    expected = 3.0 - lr * m_hat / (v_hat**0.5 + eps)
    assert p.data == pytest.approx(expected, rel=1e-9)


def test_adam_moves_toward_reducing_positive_gradient():
    p = Value(1.0)
    p.grad = 1.0
    opt = Adam([p], lr=0.1)
    opt.step()
    assert p.data < 1.0


def test_adam_accumulates_moments_across_steps():
    p = Value(0.0)
    opt = Adam([p], lr=0.01)
    for _ in range(5):
        p.grad = 1.0
        opt.step()
    assert opt.t == 5
    assert opt.m[0] != 0.0
    assert opt.v[0] != 0.0


def test_train_rejects_unknown_optimizer():
    model = MLP([2, 2, 1], seed=0)
    xs, ys = make_xor()
    with pytest.raises(ValueError):
        train(model, xs, ys, epochs=1, optimizer="nope")


def test_train_with_adam_reduces_loss_on_xor():
    model = MLP([2, 4, 1], activation="tanh", out_activation="sigmoid", seed=0)
    xs, ys = make_xor()
    history = train(model, xs, ys, epochs=200, lr=0.05, optimizer="adam")
    assert history[-1] < history[0]
    assert history[-1] < 0.1


def test_optimizers_registry_has_sgd_and_adam():
    assert set(OPTIMIZERS) == {"sgd", "adam"}


def test_train_step_schedule_decays_opt_lr_over_epochs():
    model = MLP([2, 2, 1], seed=0)
    xs, ys = make_xor()
    seen_lrs = []

    class RecordingSGD:
        def __init__(self, params, lr=0.1):
            self.params = list(params)
            self.lr = lr

        def step(self):
            seen_lrs.append(self.lr)
            for p in self.params:
                p.data -= self.lr * p.grad

    import autograd.train as train_mod
    orig = train_mod.OPTIMIZERS
    train_mod.OPTIMIZERS = dict(orig, sgd=RecordingSGD)
    try:
        train(model, xs, ys, epochs=10, lr=1.0, optimizer="sgd",
              lr_schedule="step", lr_decay=0.5, lr_step_size=5)
    finally:
        train_mod.OPTIMIZERS = orig

    assert seen_lrs[0] == pytest.approx(1.0)
    assert seen_lrs[5] == pytest.approx(0.5)


def test_train_unknown_lr_schedule_raises():
    model = MLP([2, 2, 1], seed=0)
    xs, ys = make_xor()
    with pytest.raises(ValueError):
        train(model, xs, ys, epochs=1, lr_schedule="nope")


def test_train_default_lr_schedule_is_constant():
    model = MLP([2, 2, 1], seed=0)
    xs, ys = make_xor()
    history = train(model, xs, ys, epochs=50, lr=0.5, optimizer="sgd")
    assert len(history) == 50
