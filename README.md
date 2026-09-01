# forgeai-build

autonomous build lane

An autonomous agent's own build repo — commits and PRs here come
from an unattended loop, merged only when its own CI passes.

## eulerlib

A small Python package of Project Euler solutions, one function per
problem (`eulerlib.p1()`, `eulerlib.p14()`, ...). Each function
defaults to the parameters in the original problem statement and
returns the answer. CI (`pytest`) asserts every function against its
known-correct answer — passing tests mean the solutions are actually
right, not just that the code imports.

```python
import eulerlib
eulerlib.p16()  # 1366 — digit sum of 2^1000
eulerlib.p1()  # 233168 — sum of multiples of 3 or 5 below 1000
```

Run tests locally:

```
python3 -m venv .venv && .venv/bin/pip install -e . pytest
.venv/bin/pytest -v
```
