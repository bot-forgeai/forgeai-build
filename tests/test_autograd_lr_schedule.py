import math

import pytest

from autograd.lr_schedule import make_schedule


def test_constant_schedule_never_changes():
    f = make_schedule("constant", base_lr=0.5, epochs=100)
    assert f(0) == 0.5
    assert f(50) == 0.5
    assert f(99) == 0.5


def test_step_schedule_decays_at_boundaries():
    f = make_schedule("step", base_lr=1.0, epochs=100, decay=0.5, step_size=10)
    assert f(0) == pytest.approx(1.0)
    assert f(9) == pytest.approx(1.0)
    assert f(10) == pytest.approx(0.5)
    assert f(20) == pytest.approx(0.25)


def test_step_schedule_default_step_size_derives_from_epochs():
    f = make_schedule("step", base_lr=1.0, epochs=50, decay=0.1, step_size=None)
    # default step_size is epochs // 5 == 10
    assert f(9) == pytest.approx(1.0)
    assert f(10) == pytest.approx(0.1)


def test_step_schedule_rejects_nonpositive_step_size():
    with pytest.raises(ValueError):
        make_schedule("step", base_lr=1.0, epochs=100, step_size=0)


def test_cosine_schedule_starts_high_ends_near_zero():
    f = make_schedule("cosine", base_lr=1.0, epochs=100)
    assert f(0) == pytest.approx(1.0)
    assert f(99) == pytest.approx(0.0, abs=1e-9)


def test_cosine_schedule_is_monotonically_decreasing():
    f = make_schedule("cosine", base_lr=1.0, epochs=50)
    values = [f(e) for e in range(50)]
    assert all(values[i] >= values[i + 1] - 1e-12 for i in range(len(values) - 1))


def test_cosine_schedule_matches_hand_derived_midpoint():
    f = make_schedule("cosine", base_lr=2.0, epochs=3)
    # epochs=3 -> denom=2, midpoint epoch=1 -> cos(pi/2) == 0 -> half of base_lr
    assert f(1) == pytest.approx(1.0)


def test_unknown_schedule_raises_value_error():
    with pytest.raises(ValueError):
        make_schedule("nope", base_lr=1.0, epochs=10)
