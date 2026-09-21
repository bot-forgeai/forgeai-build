import json
import random

from autograd.datasets import make_blobs, make_circles, make_xor
from autograd.nn import MLP
from autograd.train import accuracy, predict, train


def test_neuron_and_layer_parameter_counts():
    model = MLP([2, 3, 1], seed=1)
    # layer 1: 3 neurons * (2 weights + 1 bias) = 9
    # layer 2: 1 neuron * (3 weights + 1 bias) = 4
    assert len(model.parameters()) == 13


def test_forward_pass_is_deterministic_with_seed():
    m1 = MLP([2, 4, 1], seed=7)
    m2 = MLP([2, 4, 1], seed=7)
    x = [0.5, -0.3]
    assert predict(m1, x).data == predict(m2, x).data


def test_zero_grad_resets_all_parameters():
    model = MLP([2, 3, 1], seed=1)
    out = predict(model, [1.0, 1.0])
    out.backward()
    assert any(p.grad != 0.0 for p in model.parameters())
    model.zero_grad()
    assert all(p.grad == 0.0 for p in model.parameters())


def test_linear_output_activation_is_unbounded():
    model = MLP([2, 1], activation="tanh", out_activation="linear", seed=3)
    # with linear output, nothing clamps the result to [-1, 1] the way
    # tanh/sigmoid would -- just check it runs and returns a float.
    out = predict(model, [10.0, 10.0])
    assert isinstance(out.data, float)


def test_invalid_activation_raises():
    # a hidden layer is required to exercise `activation` -- the last
    # layer always uses `out_activation` instead.
    model = MLP([2, 3, 1], activation="bogus", seed=1)
    try:
        predict(model, [1.0, 1.0])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_mlp_requires_at_least_two_sizes():
    try:
        MLP([2])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_train_reduces_loss_on_xor():
    xs, ys = make_xor()
    model = MLP([2, 4, 1], activation="tanh", out_activation="sigmoid", seed=42)
    history = train(model, xs, ys, epochs=300, lr=0.5)
    assert history[-1] < history[0]
    # XOR needs a hidden layer to solve -- confirm it actually gets there,
    # not just "loss went down a little".
    assert accuracy(model, xs, ys) == 1.0


def test_train_solves_linearly_separable_blobs():
    xs, ys = make_blobs(n=40, seed=1)
    model = MLP([2, 4, 1], activation="tanh", out_activation="sigmoid", seed=1)
    train(model, xs, ys, epochs=150, lr=0.3)
    assert accuracy(model, xs, ys) >= 0.9


def test_train_makes_progress_on_circles():
    xs, ys = make_circles(n=60, seed=2)
    model = MLP([2, 8, 1], activation="tanh", out_activation="sigmoid", seed=2)
    history = train(model, xs, ys, epochs=200, lr=0.3)
    # harder than blobs (not linearly separable) -- just check real
    # learning happened, not perfect separation.
    assert history[-1] < history[0] * 0.5


def test_datasets_are_deterministic_given_a_seed():
    xs1, ys1 = make_blobs(n=10, seed=5)
    xs2, ys2 = make_blobs(n=10, seed=5)
    assert xs1 == xs2
    assert ys1 == ys2


def test_datasets_differ_across_seeds():
    xs1, _ = make_blobs(n=10, seed=1)
    xs2, _ = make_blobs(n=10, seed=2)
    assert xs1 != xs2


def test_save_load_round_trip_preserves_predictions(tmp_path):
    model = MLP([2, 4, 1], activation="tanh", out_activation="sigmoid", seed=7)
    xs = [[0.1, -0.2], [1.0, 1.0], [-0.5, 0.3]]
    before = [predict(model, x).data for x in xs]

    path = tmp_path / "model.json"
    model.save(path)
    loaded = MLP.load(path)

    after = [predict(loaded, x).data for x in xs]
    assert before == after
    assert loaded.sizes == model.sizes
    assert loaded.activation == model.activation
    assert loaded.out_activation == model.out_activation


def test_save_load_reflects_trained_weights_not_just_architecture(tmp_path):
    xs, ys = make_xor()
    model = MLP([2, 4, 1], activation="tanh", out_activation="sigmoid", seed=42)
    train(model, xs, ys, epochs=300, lr=0.5)

    path = tmp_path / "trained.json"
    model.save(path)
    loaded = MLP.load(path)

    assert accuracy(loaded, xs, ys) == accuracy(model, xs, ys) == 1.0


def test_load_rejects_parameter_count_mismatch(tmp_path):
    model = MLP([2, 4, 1], seed=1)
    path = tmp_path / "model.json"
    model.save(path)

    d = json.loads(path.read_text())
    d["sizes"] = [2, 3, 1]  # different architecture -> different param count
    path.write_text(json.dumps(d))

    try:
        MLP.load(path)
        assert False, "expected ValueError"
    except ValueError:
        pass
