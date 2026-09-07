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
.venv/bin/vitalsdash vitalsdash/sample/demo.csv
# then open http://127.0.0.1:8099
```

(`pip install -e .` registers a `vitalsdash` console command; `python -m
vitalsdash ...` still works too if you prefer.)

Point it at any CSV shaped like `timestamp,<column>,<column>,...` —
for example the output of `tools/pi_vitals.py` or
`tools/disk_writes.py` in the ForgeAI harness repo. Non-numeric
columns (like a `boot_id` UUID) are automatically left out of the
charted metrics instead of causing every row to be dropped.

Add `--threshold metric=value` (repeatable) to flag a metric's chart
when its latest value exceeds a limit, or `--compare other.csv` to
render a second CSV's charts alongside the first for each shared
metric — useful for eyeballing two boots, two machines, or before/after
a change side by side.

If a CSV has exactly one non-numeric column (like `boot_id`), its
metrics are automatically bar-charted per group in addition to the
line+histogram charts. If a CSV has more than one non-numeric column,
auto-detect can't pick one unambiguously — pass `--bar-by column` to
choose it explicitly.

Run tests locally:

```
python3 -m venv .venv && .venv/bin/pip install -e . pytest
.venv/bin/pytest -v
```

## recall

A spaced-repetition flashcard CLI using the SM-2 algorithm (the
scheduling method behind SuperMemo 2 and, in modified form, Anki). A
deck is a plain JSON file; each card tracks its own interval,
repetition count, and ease factor, and is only shown again once due.

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/recall --deck mydeck.json add "capital of Peru" "Lima"
.venv/bin/recall --deck mydeck.json review   # shown once due
.venv/bin/recall --deck mydeck.json stats
.venv/bin/recall --deck mydeck.json list     # preview all cards, no reviewing
.venv/bin/recall --deck mydeck.json import cards.txt   # add cards from a text file
.venv/bin/recall --deck mydeck.json export cards.txt   # write all cards to a text file
.venv/bin/recall decks                                 # list every deck used so far
```

`--deck` defaults to `recall_deck.json` in the current directory.
`review` walks every due card, waits for you to reveal the answer,
then asks for a 0-5 recall-quality rating that determines the next
interval — a failed recall (0-2) resets the card to review again
tomorrow; a successful one (3-5) pushes the interval out further,
scaled by the ease factor. `list` shows every card sorted by due
date, each marked `due` or `upcoming`, without triggering a review.
`import`/`export` use a plain text format, one card per line as
`front<TAB>back`; blank lines and lines starting with `#` are
ignored on import, so exported decks can be hand-edited or merged
before re-importing.

Multi-deck support: any `add`, `review`, or `import` run registers
its `--deck` path in a registry file (`--registry`, defaults to
`recall_registry.json` in the current directory) under a name
derived from the deck's filename, or `--deck-name` if you want to
pick one explicitly. `recall decks` then lists every deck registered
so far with its total and due-today card counts, so you can keep
several decks (e.g. one per subject) without memorizing their paths.

## ttt

A two-player tic-tac-toe game played over a TCP socket — one process
hosts, two others join as players (from different terminals, or
different machines on the same LAN). Unlike eulerlib/vitalsdash/recall,
the interesting part here is the networked protocol and concurrent
per-connection state, not a CSV or a JSON file.

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/ttt serve --host 0.0.0.0 --port 5050   # on the host machine
.venv/bin/ttt join <host-ip> --port 5050         # from each player's terminal
```

`serve` blocks waiting for two connections, then relays moves between
them: each `MOVE <0-8>` is validated server-side (right player's turn,
cell free, game not already over) and the resulting board is broadcast
to both players after every valid move, along with whose turn it is
or the final result (`WIN:X`, `WIN:O`, `DRAW`). If one player
disconnects mid-game the other gets an `OPPONENT_LEFT` notice instead
of hanging. `join` renders the board as a 3x3 grid and prompts for a
cell number each turn.
