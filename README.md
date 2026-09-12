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

For solo play, `ttt ai <host> --port 5050` connects as an automated
opponent (perfect-play minimax over the 9-cell board — it never loses,
so at best a human can force a draw) instead of a second human. It
speaks the same socket protocol as `join`, so a solo player runs
`serve`, then `join` in one terminal and `ai` in another.

Any connection accepted after a game already has its two players joins
as a read-only spectator instead of a third player: `ttt watch <host>
--port 5050` streams the same board updates the players see (and an
`OPPONENT_LEFT` notice if a player disconnects) without being able to
move. A spectator's own input is silently ignored server-side.

`serve --best-of N` turns a single connected pair into a match: the
same two connections replay on a fresh board after each game (a draw
doesn't count for either side and just triggers a replay) until one
player reaches a majority of N wins, broadcasting `SCORE <x> <o>`
after every game and `MATCH_OVER <X|O|TIE>` once it's decided — capped
at `2*N` games total so two evenly-matched players who just keep
drawing (e.g. two perfect-play AIs) can't replay forever. `ttt ai`
exits after a single game by default; pass `--match` so it keeps
playing across the whole match instead.

## shortlink

A URL shortener with click tracking, backed by SQLite instead of the
CSV/JSON files the earlier projects use — the interesting part here is
persistent relational state shared across concurrent HTTP requests,
not a chart or a socket protocol.

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/shortlink --db links.db --port 8100
```

Then visit `http://127.0.0.1:8100/` for a page that shortens a URL and
lists every link created so far with its click count. The same
functionality is available directly over HTTP:

```
curl -X POST http://127.0.0.1:8100/api/shorten -d '{"url": "https://example.com"}'
# -> {"code": "aB3xY9", "short_url": "/aB3xY9"}
curl -i http://127.0.0.1:8100/aB3xY9          # 302 redirect, records a click
curl http://127.0.0.1:8100/api/stats/aB3xY9   # {"clicks": 1, ...}
curl http://127.0.0.1:8100/api/links          # every link, newest first
```

`POST /api/shorten` takes an optional `"code"` field to request a
specific short code instead of a random one; a conflicting request
gets a 409. It also takes an optional `"ttl_seconds"` field — if
given, the link expires that many seconds after creation. Visiting an
expired link returns `410 Gone` instead of redirecting, and
`/api/stats/<code>` and `/api/links` both report an `expires_at` /
`expired` field so you can tell a live link from an expired one
without waiting for the 410. `ThreadingHTTPServer` handles each
request on its own thread, so all database access goes through a
single lock — sqlite3 tolerates being opened across threads
(`check_same_thread=False`) but not being used by more than one at a
time.

`GET /qr/<code>` renders that code's short URL as an SVG QR code (no
Pillow or other raster dependency — the `qrcode` package's
`SvgPathImage` factory outputs plain SVG paths). The target URL is
built from the request's own `Host` header, so scanning the code
resolves correctly whether the server is bound to `127.0.0.1` or a
LAN address. The homepage embeds each link's QR code as a thumbnail
next to its click count.

For a LAN-reachable demo — so a phone or another machine on the same
network can scan a QR code and actually load the link — bind to every
interface instead of just localhost:

```
.venv/bin/shortlink --host 0.0.0.0 --port 8100
```

Startup prints the LAN IP it detected (via a UDP "connect" to a public
address, which never sends data but reveals which interface the OS
would route through) alongside the localhost URL, so you know what to
type into another device's browser or point a QR scanner at. This
still respects LIMITS.md — bound to the Pi's own LAN address, never
port-forwarded or tunneled beyond it.

## quest

A text-adventure engine — a command parser and room/item graph, not a
CSV, socket protocol, or SQL table. A game is a JSON world file (rooms,
exits, items, an optional win condition); the engine interprets typed
commands against it and a save file captures a full playthrough,
including anything the player mutated (unlocked doors, moved items).

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/quest play
```

That launches the bundled sample game, a small four-room dungeon.
Commands: `go <direction>` (also `n`/`s`/`e`/`w`/`u`/`d` as shorthand),
`look`, `take <item>`, `drop <item>`, `inventory`, `examine <item>`,
`unlock <direction> with <item>`, `talk to <person>`,
`give <item> to <person>`, `save [path]`, `quit`. Item and NPC names
match by substring, case-insensitively, so `take key` matches "brass
key". NPCs can trade: giving an NPC the item they want (if any) may
hand back another item in return, and their dialogue can change after
the trade. An NPC can also wander: giving it a `"wander_rooms"` list in
the world file makes it move to a random room from that list each time
the player takes a turn, so it won't always be where you left it.

```
.venv/bin/quest play --world mygame.json   # play a different world file
.venv/bin/quest play --load save.json      # resume a saved game
```

Exits can be locked to a specific item id; `unlock` only succeeds with
that exact item in inventory, and the unlock persists across `save`/
`--load` since the save file snapshots the whole mutated world, not
just the player's position. A world file can declare a `"win"` room
(and optionally a required item) — reaching it ends the session with
`*** You win! ***`.

## babble

A word-level Markov chain text generator — a trained model with
persistent state (transition frequencies serialized to JSON), not a
game, a socket protocol, or a database. Train it on any plain-text
corpus and it generates new text by walking the chain of word
transitions it learned, with the same probabilities the source text
had.

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/babble train mycorpus.txt --order 2 --out model.json
.venv/bin/babble generate model.json --length 40
```

`--order N` controls how many preceding words the model looks at
before choosing the next one (default 2); higher orders produce more
coherent but less novel text, since longer contexts have fewer
plausible continuations. `train` accepts multiple corpus files at
once. `generate --seed "some words"` starts from an exact phrase
instead of a random sentence-starting point (the phrase must have
exactly `order` words); `--count N` generates several lines in one
call. `babble info model.json` reports the model's order, vocabulary
size, and number of distinct states without generating anything.

`--unit char` trains on individual characters instead of whole words
(`--seed` then takes a raw string of exactly `order` characters, and
generated output is joined without spaces) — useful for corpora too
small to have meaningful word-level statistics, or for
invented-word/name generation. `train`, `merge`, and `generate` all
refuse to mix a word-level model with a char-level one.

## ssg

A small static site generator — a filesystem content pipeline, not a
game, a socket protocol, or a trained model. It parses markdown files
with a lightweight front-matter header, renders them through a subset
markdown-to-HTML converter, applies them to `{{ placeholder }}`
templates, and writes plain static HTML you can host anywhere.

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/ssg --site ssg/site new "My First Post"
.venv/bin/ssg --site ssg/site --title "My Blog" build
.venv/bin/ssg --site ssg/site --title "My Blog" serve --port 8000
```

A site directory holds `content/` (markdown files, front matter like
`title:`/`date:`, searched recursively), an optional `templates/`
(`page.html` and `index.html`; falls back to a built-in default when
missing), and an optional `static/` copied as-is into the build
output. `build` writes one HTML file per content page plus an
`index.html` listing every page sorted newest-first by `date`.
`serve` builds and then serves the output directory over a local
HTTP server (binds to `127.0.0.1` by default; LAN-reachable with
`--host 0.0.0.0`, per the same LAN-only constraint as shortlink's
demo mode). `new TITLE` scaffolds a dated front-matter stub under
`content/posts/`.

The markdown subset covers headers, paragraphs, unordered lists,
fenced code blocks, and inline `**bold**`/`*italic*`/`` `code` ``/
`[links](url)` — enough for real prose, not a CommonMark-complete
parser. Raw HTML in content is escaped, not executed.

Pass `--base-url` (a global flag, before the subcommand) to also
write an RSS 2.0 `feed.xml` alongside the built pages, e.g.
`ssg --site ssg/site --base-url https://example.com build`. Feed
links need an absolute URL, so the feed is skipped without one.

## kvlog

A log-structured key-value store — an append-only write-ahead log on
disk with a durability/crash-recovery model, not a game, a socket
protocol, a trained model, or a filesystem pipeline. Every `put`/
`delete` is appended as a length-prefixed, checksummed record and
flushed immediately; the in-memory index is rebuilt from scratch by
replaying the log on open.

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/kvlog --db mydata.db put name ada
.venv/bin/kvlog --db mydata.db get name
.venv/bin/kvlog --db mydata.db keys
.venv/bin/kvlog --db mydata.db dump
.venv/bin/kvlog --db mydata.db compact
```

Each record on disk is a 4-byte length prefix, a JSON payload
(`{"op": "put"|"delete", "key": ..., "value": ...}`), and a trailing
CRC32 checksum. If a write is interrupted mid-record (a crash, a
killed process), the next open detects the incomplete or corrupt tail
and silently drops it rather than failing to open or corrupting
earlier, already-flushed records — everything before the crash is
still there. `compact` rewrites the log with exactly one `put` per
live key (dropping overwritten/deleted history), written to a temp
file and swapped in with `os.replace` so a crash mid-compaction never
leaves a partial file at the real path.

A page marked `draft: true` in its front matter is excluded from the
build, the index, and the feed by default; pass the global `--drafts`
flag (e.g. `ssg --site ssg/site --drafts serve`) to include drafts too,
for local preview before publishing. `new TITLE --draft` scaffolds a
new post already marked as a draft.

A page's front-matter `tags:` field (a comma-separated string, e.g.
`tags: python, tutorial`) generates a listing page per tag under
`tags/<tag>.html` plus a `tags/index.html` linking every tag with its
page count; the default page template links each of a page's own tags
back to its tag listing. Sites with no tagged pages get no `tags/`
directory at all.

`ssg --site ssg/site watch` rebuilds once, then polls `content/`,
`templates/`, and `static/` for changes (added, removed, or edited
files) and rebuilds again on each change, until interrupted with
Ctrl+C. `serve --watch` runs the same polling rebuild in a background
thread alongside the HTTP server, so editing a post and reloading the
browser shows the new content without restarting anything. `--interval`
sets the poll period in seconds (default: 1.0) for either mode.
