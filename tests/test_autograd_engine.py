from autograd.engine import Value


def numerical_grad(f, x, h=1e-6):
    return (f(x + h) - f(x - h)) / (2 * h)


def test_add_grad():
    a = Value(2.0)
    b = Value(3.0)
    c = a + b
    c.backward()
    assert a.grad == 1.0
    assert b.grad == 1.0


def test_mul_grad():
    a = Value(2.0)
    b = Value(3.0)
    c = a * b
    c.backward()
    assert a.grad == 3.0
    assert b.grad == 2.0


def test_sub_neg():
    a = Value(5.0)
    b = Value(2.0)
    c = a - b
    assert c.data == 3.0
    c.backward()
    assert a.grad == 1.0
    assert b.grad == -1.0


def test_pow_grad():
    a = Value(3.0)
    c = a ** 3
    assert c.data == 27.0
    c.backward()
    assert abs(a.grad - 27.0) < 1e-9  # d/dx x^3 = 3x^2 = 27


def test_div_grad():
    a = Value(6.0)
    b = Value(3.0)
    c = a / b
    assert c.data == 2.0
    c.backward()
    assert abs(a.grad - (1 / 3)) < 1e-9
    assert abs(b.grad - (-6 / 9)) < 1e-9


def test_tanh_grad_matches_numerical():
    x0 = 0.7

    def f(x):
        return __import__("math").tanh(x)

    expected = numerical_grad(f, x0)
    a = Value(x0)
    out = a.tanh()
    out.backward()
    assert abs(a.grad - expected) < 1e-4


def test_relu_grad():
    pos = Value(2.0)
    out_pos = pos.relu()
    out_pos.backward()
    assert pos.grad == 1.0

    neg = Value(-2.0)
    out_neg = neg.relu()
    out_neg.backward()
    assert neg.grad == 0.0


def test_sigmoid_grad_matches_numerical():
    x0 = 0.3

    def f(x):
        return 1.0 / (1.0 + __import__("math").exp(-x))

    expected = numerical_grad(f, x0)
    a = Value(x0)
    out = a.sigmoid()
    out.backward()
    assert abs(a.grad - expected) < 1e-4


def test_exp_grad():
    a = Value(1.0)
    out = a.exp()
    out.backward()
    assert abs(a.grad - __import__("math").e) < 1e-9


def test_composite_expression_grad_matches_numerical():
    # f(x) = tanh(x * 2 + 1) ** 2, check dx via central difference.
    def f(x):
        import math
        return math.tanh(x * 2 + 1) ** 2

    x0 = 0.4
    expected = numerical_grad(f, x0)

    a = Value(x0)
    out = (a * 2 + 1).tanh() ** 2
    out.backward()
    assert abs(a.grad - expected) < 1e-4


def test_reused_value_accumulates_grad():
    # x used twice: y = x + x should give dy/dx = 2, not 1 (a classic
    # bug if backward() overwrites instead of accumulating grad).
    x = Value(3.0)
    y = x + x
    y.backward()
    assert x.grad == 2.0


def test_radd_rmul_rsub_rtruediv():
    a = Value(4.0)
    assert (2 + a).data == 6.0
    assert (2 * a).data == 8.0
    assert (10 - a).data == 6.0
    assert (8 / a).data == 2.0


def test_pow_rejects_value_exponent():
    a = Value(2.0)
    b = Value(3.0)
    try:
        a ** b
        assert False, "expected TypeError"
    except TypeError:
        pass
