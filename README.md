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

**Status: feature-complete.** It served its purpose as the first
build-lane exercise (real CI, real merged PRs, one function per
problem through p58). No more Project Euler problems will be added
here — new work goes into other packages in this repo instead.

## vitalsdash

A standalone local dashboard for any timestamp+metrics CSV — point it
at a log of numeric readings over time and it serves a page charting
each column, with zero external dependencies (stdlib `http.server`
only, no CDN scripts, no build step).

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m vitalsdash vitalsdash/sample/demo.csv
# then open http://127.0.0.1:8099
```

Point it at any CSV shaped like `timestamp,<metric>,<metric>,...` —
for example the output of `tools/pi_vitals.py` in the ForgeAI harness
repo.

Run tests locally:

```
python3 -m venv .venv && .venv/bin/pip install -e . pytest
.venv/bin/pytest -v
```
