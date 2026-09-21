"""Optimizers that update autograd.Value parameters in place from their
accumulated .grad, given a model's .parameters() list."""


class SGD:
    """Plain gradient descent: p.data -= lr * p.grad."""

    def __init__(self, params, lr=0.1):
        self.params = list(params)
        self.lr = lr

    def step(self):
        for p in self.params:
            p.data -= self.lr * p.grad


class Adam:
    """Adam (Kingma & Ba, 2015): per-parameter adaptive learning rates
    from running estimates of the gradient's first and second moments,
    each bias-corrected for their startup-at-zero initialization.
    """

    def __init__(self, params, lr=0.001, betas=(0.9, 0.999), eps=1e-8):
        self.params = list(params)
        self.lr = lr
        self.beta1, self.beta2 = betas
        self.eps = eps
        self.t = 0
        self.m = [0.0] * len(self.params)
        self.v = [0.0] * len(self.params)

    def step(self):
        self.t += 1
        b1, b2 = self.beta1, self.beta2
        bias1 = 1 - b1 ** self.t
        bias2 = 1 - b2 ** self.t
        for i, p in enumerate(self.params):
            g = p.grad
            self.m[i] = b1 * self.m[i] + (1 - b1) * g
            self.v[i] = b2 * self.v[i] + (1 - b2) * g * g
            m_hat = self.m[i] / bias1
            v_hat = self.v[i] / bias2
            p.data -= self.lr * m_hat / (v_hat ** 0.5 + self.eps)


OPTIMIZERS = {"sgd": SGD, "adam": Adam}
