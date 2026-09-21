"""Reverse-mode automatic differentiation over scalar values.

Each Value node remembers the operation that produced it and a local
backward function; calling backward() on the final output walks the
graph in reverse topological order and accumulates dL/dx into every
node's .grad, the same technique real deep learning frameworks use
(just without tensors -- one float per node).
"""
import math


class Value:
    def __init__(self, data, _children=(), _op=""):
        self.data = float(data)
        self.grad = 0.0
        self._backward = lambda: None
        self._prev = set(_children)
        self._op = _op

    def __repr__(self):
        return f"Value(data={self.data}, grad={self.grad})"

    @staticmethod
    def _wrap(x):
        return x if isinstance(x, Value) else Value(x)

    def __add__(self, other):
        other = Value._wrap(other)
        out = Value(self.data + other.data, (self, other), "+")

        def _backward():
            self.grad += out.grad
            other.grad += out.grad

        out._backward = _backward
        return out

    def __radd__(self, other):
        return self + other

    def __neg__(self):
        return self * -1

    def __sub__(self, other):
        return self + (-Value._wrap(other))

    def __rsub__(self, other):
        return Value._wrap(other) + (-self)

    def __mul__(self, other):
        other = Value._wrap(other)
        out = Value(self.data * other.data, (self, other), "*")

        def _backward():
            self.grad += other.data * out.grad
            other.grad += self.data * out.grad

        out._backward = _backward
        return out

    def __rmul__(self, other):
        return self * other

    def __pow__(self, power):
        if not isinstance(power, (int, float)):
            raise TypeError("only int/float powers are supported")
        out = Value(self.data ** power, (self,), f"**{power}")

        def _backward():
            self.grad += (power * self.data ** (power - 1)) * out.grad

        out._backward = _backward
        return out

    def __truediv__(self, other):
        return self * Value._wrap(other) ** -1

    def __rtruediv__(self, other):
        return Value._wrap(other) * self ** -1

    def exp(self):
        e = math.exp(self.data)
        out = Value(e, (self,), "exp")

        def _backward():
            self.grad += e * out.grad

        out._backward = _backward
        return out

    def tanh(self):
        t = math.tanh(self.data)
        out = Value(t, (self,), "tanh")

        def _backward():
            self.grad += (1 - t * t) * out.grad

        out._backward = _backward
        return out

    def relu(self):
        r = self.data if self.data > 0 else 0.0
        out = Value(r, (self,), "relu")

        def _backward():
            self.grad += (1.0 if self.data > 0 else 0.0) * out.grad

        out._backward = _backward
        return out

    def sigmoid(self):
        s = 1.0 / (1.0 + math.exp(-self.data))
        out = Value(s, (self,), "sigmoid")

        def _backward():
            self.grad += s * (1 - s) * out.grad

        out._backward = _backward
        return out

    def backward(self):
        order = []
        seen = set()

        def build(node):
            if id(node) not in seen:
                seen.add(id(node))
                for child in node._prev:
                    build(child)
                order.append(node)

        build(self)
        self.grad = 1.0
        for node in reversed(order):
            node._backward()
