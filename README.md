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

Every card tracks its `lapses` count -- how many times it's been
rated a failed recall (0-2) during `review`. A card that keeps
lapsing despite repeated review is a "leech" (the Anki term): usually
a sign the card itself is malformed (too vague, testing two facts at
once) rather than a memory problem. `recall stats` reports the
current leech count, and `recall leeches [--threshold N]` (default
4, matching Anki's own default) lists them worst-first so you can
rewrite or delete them instead of reviewing the same failing card
forever.

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

Spun off into its own repo: [bot-forgeai/md-ssg](https://github.com/bot-forgeai/md-ssg).

## kvlog

A log-structured key-value store — an append-only write-ahead log on
disk with a durability/crash-recovery model, not a game, a socket
protocol, a trained model, or a filesystem pipeline. Every `put`/
`delete` is appended as a length-prefixed, checksummed record and
flushed (and, by default, `fsync`'d) immediately; the in-memory index
is rebuilt from scratch by replaying the log on open.

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/kvlog --db mydata.db put name ada
.venv/bin/kvlog --db mydata.db get name
.venv/bin/kvlog --db mydata.db keys
.venv/bin/kvlog --db mydata.db dump
.venv/bin/kvlog --db mydata.db prefix user:
.venv/bin/kvlog --db mydata.db range --start a --end m
.venv/bin/kvlog --db mydata.db compact
```

`prefix` lists every key/value pair whose key starts with a given
string; `range` lists every pair with `start <= key <= end`, where
either `--start` or `--end` may be omitted for an unbounded side.
Both operate on the in-memory sorted index, not a scan of the log.

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

### fsync policy

By default every write calls `os.fsync` after flushing, so a `put` or
`delete` only returns once the record is actually on disk — a power
loss right after a successful write can't lose it, only a crash mid-write
(which the checksum/length-prefix format already tolerates). Pass
`--fsync never` to skip the `fsync` call and just flush to the OS page
cache: writes are still visible to the same process immediately and
still survive a process crash, but a power loss before the OS decides
to write the page cache back to disk can lose the most recent writes.
This trades that guarantee for throughput, since `fsync` is a real
syscall cost per write:

```
.venv/bin/kvlog --db mydata.db --fsync never put name ada
.venv/bin/kvlog --db shared.db --fsync never serve --port 9999
```

`--fsync` is a global flag (before the subcommand) and applies to
`compact` as well as `put`/`delete`. It only affects a local `--db`;
a `--remote` client's writes are governed by whatever policy the
server it's talking to was started with.

### Remote access

`kvlog serve` exposes a `--db` file over a threaded TCP server so more
than one client (or a client on another LAN device) can read/write the
same store without sharing a filesystem. Every other subcommand
accepts `--remote HOST:PORT` to talk to a running server instead of
opening `--db` locally:

```
.venv/bin/kvlog --db shared.db serve --port 9999
# on the same or another LAN machine:
.venv/bin/kvlog --remote 127.0.0.1:9999 put name ada
.venv/bin/kvlog --remote 127.0.0.1:9999 get name
```

The wire protocol is one JSON request/response object per line
(`kvlog/protocol.py`'s `dispatch` is the pure logic shared by the
server and its tests). A single `KVStore` instance is shared across
all connections, guarded by one lock, since the store's file handle
and in-memory index aren't safe for concurrent access on their own.
Pass `--host 0.0.0.0` to `serve` to accept connections from elsewhere
on the LAN (still LAN-only per this project's network limits — no
port-forwarding or tunneling).

### Replication

`kvlog replicate` runs a standalone replica that continuously pulls
writes from a leader's `serve` and applies them to its own local
`--db` — a separate, independently-readable copy that stays close to
up to date without sharing a filesystem with the leader:

```
# leader:
.venv/bin/kvlog --db primary.db serve --port 9999
# elsewhere, on the same or another LAN machine:
.venv/bin/kvlog --db replica.db replicate --leader 127.0.0.1:9999
.venv/bin/kvlog --db replica.db get name
```

This is poll-based, not push-based: the replica periodically (every
`--poll-interval` seconds, default 1.0) sends a `sync` request naming
the byte offset it has already applied, and the leader replies with
every record appended since then plus its current offset. The leader
has no notion of which replicas exist or are currently connected —
a replica can disconnect, crash, or restart at any time and just
resumes from its own last-applied offset (persisted in a
`<db>.replica_offset` sidecar file next to the replica's `--db`),
rather than needing a full resync. The tradeoff for this simplicity is
up to one poll interval of staleness rather than the leader pushing
writes the instant they happen.

Replication survives the leader running `compact`: the leader tracks a
generation counter (bumped once per `compact()`, persisted alongside
its log so it's correct even after a restart) and reports it in every
`sync` response. A replica persists the last generation it saw next to
its cursor; if the leader's generation has moved on since the last
sync, the byte-offset cursor is no longer meaningful against the
rewritten log, so the replica clears its local state and does a fresh
full sync from offset 0 before applying anything further — no manual
intervention needed.

## toylang

A tiny interpreted scripting language — a lexer, a recursive-descent
parser, and a tree-walking interpreter, not a game, a database, or a
trained model. Variables, arithmetic/comparison/logical operators,
`if`/`else`, `while`, functions (including closures and recursion),
lists, and a handful of builtins (`print`, `len`, `push`, `pop`).

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/toylang toylang/sample.tl
.venv/bin/toylang               # interactive REPL
```

A script looks like:

```
func fib(n) {
    if (n <= 1) { return n; }
    return fib(n - 1) + fib(n - 2);
}
print(fib(10));
```

Functions close over their defining scope, so a function returned
from another function keeps access to that function's locals:

```
func make_counter() {
    let count = 0;
    func increment() { count = count + 1; return count; }
    return increment;
}
let c = make_counter();
print(c(), c(), c());   # 1 2 3
```

Lists are mutable and zero-indexed, with `[]` literals, `[i]` indexing
(also works for reading a character out of a string), and `push`/`pop`
builtins:

```
let xs = [1, 2, 3];
push(xs, 4);
xs[0] = 99;
print(xs);        # [99, 2, 3, 4]
print(len(xs));   # 4
print(pop(xs));   # 4
```

Indexing out of range, or index-assigning into a non-list, raises a
runtime error rather than silently corrupting state.

A small standard library of builtins covers strings, numbers, and
ranges: `upper`/`lower`/`trim`, `split`/`join`, `contains`
(substring or list membership), `str`/`num` (conversion), `abs`/
`floor`/`sqrt`/`min`/`max`, and `range(end)`/`range(start, end)` for
generating a list to loop over:

```
let xs = range(1, 4);           # [1, 2, 3]
print(join(split("a,b,c", ","), " - "));  # a - b - c
print(sqrt(16) + max(1, 9, 3)); # 13
```

`toylang` with no file argument starts a REPL; each line is evaluated
in the same persistent environment, so variables and functions defined
on one line are visible on the next. Runtime errors (undefined
variables, wrong argument counts, division by zero, non-numeric
arithmetic, calling a non-function) and syntax errors both print a
one-line `error: ...` message and exit non-zero rather than showing a
Python traceback.

The REPL supports multi-line input: if a line leaves an open
`(`/`{`/`[` or an unterminated string literal, the prompt switches to
`... ` and keeps buffering until the brackets balance, so a `func`,
`if`, or `while` block can be typed the same way it would be in a
script:

```
> func greet(name) {
...   print("hi " + name);
... }
> greet("ada");
hi ada
```

## searchlite

A tiny full-text search engine — an inverted index over indexed
documents, ranked by TF-IDF, not a graph, a socket protocol, or a
language interpreter. Index plain-text files, then search them and
get results ranked by relevance.

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/searchlite --index notes.json add-dir ./notes --ext .txt,.md
.venv/bin/searchlite --index notes.json search "quick fox"
```

Each `search` result line is `score<TAB>doc_id<TAB>preview`, ranked
highest score first. `add`/`add-dir` build up an index incrementally
(re-indexing a `doc_id` replaces its old content rather than
duplicating it); `remove DOC_ID` drops a document; `stats` reports the
document and term counts. The index is a single JSON file
(`--index`, default `searchlite.json`) so it can be inspected, backed
up, or checked into version control like any other data file.

Scoring is a standard smoothed TF-IDF: a term's contribution to a
document's score is its raw frequency in that document times
`log((N + 1) / (df + 1)) + 1`, where `N` is the total document count
and `df` is how many documents contain the term — so rarer terms
that appear across fewer documents count for more than common ones.

`search --snippet` swaps the plain leading preview for a short excerpt
built around the first place a query term actually appears in the
document, with each matched term wrapped in `**asterisks**` — useful
when the query terms don't happen to occur near the start of a longer
document:

```
.venv/bin/searchlite --index notes.json search "quick fox" --snippet
```

`search --rank {tfidf,bm25}` (default `tfidf`) switches the scoring
method. BM25 adds two things TF-IDF lacks: term-frequency saturation
(a term matching 100 times in a document scores only a little higher
than matching 10 times, not 10x higher) and document-length
normalization (a long document isn't unfairly favored just for having
more words overall, and isn't unfairly penalized either) via the
standard `k1=1.5, b=0.75` constants:

```
.venv/bin/searchlite --index notes.json search "quick fox" --rank bm25
```

`search --phrase` requires the query terms to appear as an exact
consecutive sequence (after the same tokenization/stopword-filtering
used elsewhere), not just anywhere in the document — results are
ranked by phrase occurrence count instead of tfidf/bm25. Backed by a
positional index (`Index.positions`, term -> doc_id -> token
positions) built alongside the regular postings on every `add`; an
index saved before this feature existed has no positions data, so
`--phrase` searches against it find nothing until the documents are
re-added:

```
.venv/bin/searchlite --index notes.json search "quick brown fox" --phrase
```

## vcslite

A tiny version-control system — a content-addressable object store
plus a linear commit history, not a CSV/HTTP dashboard, a socket
protocol, or a search index. The mechanics are genuinely different
from every prior project here: objects (blobs, trees, commits) are
identified by the SHA-1 hash of their own content and stored
zlib-compressed under `.vcslite/objects/<sha[:2]>/<sha[2:]>`, the same
scheme git itself uses, so identical content is only ever stored once.

```
python3 -m venv .venv && .venv/bin/pip install -e .
cd myproject
../.venv/bin/vcslite init
echo "hello" > a.txt
../.venv/bin/vcslite add a.txt
../.venv/bin/vcslite commit -m "first commit"
../.venv/bin/vcslite log
```

`add PATH...` (or `add .` for everything under the working tree)
stages files into `.vcslite/index.json`, a flat JSON map of path to
blob sha. `commit -m MSG` snapshots the current index into a tree
object and a commit object linking back to the previous commit,
refusing to commit when nothing is staged or the tree is unchanged
since the last commit. `status` classifies every path as staged
(differs from HEAD), modified (working copy differs from what's
staged), untracked, or deleted (plus the branch `status` is on, or
where HEAD is detached). `diff` shows a unified diff of staged changes
against HEAD. `log` walks the commit chain from HEAD back to the
first commit.

`branch` lists every branch, marking the current one with `*`;
`branch NAME` creates a new branch pointing at HEAD's commit.
`checkout NAME` switches HEAD to that branch and restores the working
tree/index to its tip; `checkout -b NAME [START]` creates a branch
(at HEAD, or at `START` if given) and switches to it in one step,
mirroring git's own `-b` shorthand. `checkout SHA` (a full or
unambiguous short prefix) restores the working tree to that exact
commit and detaches HEAD — a commit made in this state advances HEAD
itself without moving any branch, so it's easy to end up with commits
no branch points at (same as git's own detached-HEAD footgun).

Like git, vcslite nests one tree object per directory rather than one
flat tree per commit — a tree object is a sorted list of entries, each
either a `blob` (a file) or another `tree` (a subdirectory). Because
objects are content-addressed, an unmodified subdirectory hashes to
the exact same tree object across commits and is only ever stored (or
transferred, via `push`/`fetch`) once, no matter how many commits
share it unchanged.

A `.vcsliteignore` file at the repo root (one glob pattern per line;
blank lines and `#` comments ignored) excludes matching paths from
`add .` and from `status`'s untracked list — a pattern matches either
the whole relative path or any single path component, so both
`*.log` and a bare directory name like `build` work as expected.
Naming an ignored file explicitly (`add debug.log`) still stages it,
and a file already tracked before being added to `.vcsliteignore`
keeps showing up normally in `status` (as modified/staged/deleted) —
the ignore file only ever hides new, never-tracked paths.

`merge BRANCH` merges another branch into the current one. If the
current branch is a plain ancestor of `BRANCH`, it just fast-forwards
(moves the branch ref, no new commit). Otherwise it finds the nearest
common ancestor commit and does a 3-way merge of the two trees against
it, path by path: a path only one side touched is taken as-is, and a
path both sides changed identically (or both deleted) needs no
resolution. A path both sides changed *differently* becomes a
conflict: vcslite writes git-style `<<<<<<< HEAD` / `=======` /
`>>>>>>> BRANCH` markers into the working-tree file (each side's full
content, since vcslite doesn't attempt a line-level merge) and stops
short of committing. `status` shows an in-progress merge and which
paths are still conflicted; after hand-editing a conflicted file,
`add` it and `commit` as normal to finish the merge as a commit with
two parents (`log` marks these `(merge: ..., ...)`). `merge --abort`
throws away an unresolved merge and restores the working tree to
where it was before `merge` ran.

`clone SRC DEST` copies every branch's objects from the repo at `SRC`
into a brand-new repo at `DEST`, checks out `SRC`'s current branch
there, and registers `SRC` as a remote named `origin` — no networking
involved, a "remote" is just another vcslite repo's path on the local
filesystem (or anywhere reachable through it). `remote add NAME PATH`
registers additional remotes; a bare `remote` lists them. `push REMOTE
[BRANCH]` (defaults to the current branch) copies missing objects over
to the remote and moves its ref there, but is fast-forward-only —
rejected if the remote's current tip for that branch isn't an ancestor
of the local one, the same guard rail git's own non-force push uses.
Like pushing into a non-bare git repo, push never touches the remote's
own working tree or index — its next `checkout`/`status` there will
see the moved ref immediately, but its files only catch up once it
checks out again. `fetch REMOTE` copies every branch's missing objects
in the other direction and records them under `refs/remotes/<name>/
<branch>` without touching the current branch or working tree; `pull
REMOTE BRANCH` is `fetch` followed by `merge`-ing that remote-tracking
ref into the current branch (fast-forwarding when possible, doing a
real 3-way merge — conflict markers and all — otherwise).

## chesslite

A small chess engine — full legal move generation (castling, en
passant, promotion) with check/checkmate/stalemate detection, plus a
minimax-with-alpha-beta AI opponent. The interesting part is the game
logic itself: pseudo-legal moves per piece type are filtered down to
legal ones by simulating each move and checking whether it leaves the
mover's own king in check, which is also how castling's "can't
castle through/into check" rule and checkmate/stalemate detection
(no legal moves, with or without check) fall out for free.

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/chesslite play                       # two human players
.venv/bin/chesslite play --ai b --depth 3       # play White against the engine
```

Moves are entered in coordinate notation (`e2e4`, or `e7e8q` to
promote to a queen — `q`/`r`/`b`/`n` are accepted, defaulting to a
queen if omitted). The board is a dict of `(file, rank)` coordinates
to single-character pieces (uppercase White, lowercase Black), with
castling rights, the en-passant target square, and a halfmove clock
(for the 50-move draw rule) tracked alongside it. A game also draws on
threefold repetition (`Board.position_key()` hashes piece placement,
side to move, castling rights, and en passant target; `Game` counts
how many times each key has occurred) and on insufficient material
(bare kings, king-plus-minor-piece, or same-colored-bishop endgames
where neither side can force checkmate). An illegal move (wrong syntax
or an illegal destination) prints a clean `error: ...` message and
reprompts rather than crashing.

`chesslite.ai.choose_move(board, color, depth=N)` runs a fixed-depth
negamax search with alpha-beta pruning over a material-plus-center-
control evaluation — not a strong engine, but a real adversarial
search rather than a random-legal-move bot, and deep enough (depth 2
by default, `--depth` to go further) to reliably punish an undefended
free capture.

`chesslite` also plays over a TCP socket, following the same
serve/join/ai shape as `ttt`:

```
.venv/bin/chesslite serve --host 0.0.0.0 --port 5060   # on the host machine
.venv/bin/chesslite join <host-ip> --port 5060         # White's terminal
.venv/bin/chesslite join <host-ip> --port 5060         # Black's terminal
```

`serve` accepts exactly two connections (White first, then Black) and
relays moves between them: each `MOVE <e2e4-style text>` is validated
server-side (right player's turn, legal per the same engine `play`
uses) and the resulting position is broadcast to both players after
every valid move as a FEN string plus a status (`TURN:w`/`TURN:b`,
`CHECK:w`/`CHECK:b`, `CHECKMATE:w`/`CHECKMATE:b`, `STALEMATE`, or
`DRAW`) — the FEN lets each client reconstruct the exact board,
including castling rights and the en-passant target, without
replaying move history. If one player disconnects mid-game the other
gets an `OPPONENT_LEFT` notice instead of hanging.

For solo play, `chesslite ai <host> --port 5060 [--depth N]` connects
as an automated opponent instead of a second human — it speaks the
same protocol as `join`, reconstructing the board from each broadcast
FEN and running the same `choose_move` search `play --ai` uses.

`chesslite play --pgn game.pgn` records the game in Standard Algebraic
Notation (`Game.san`/`Game.to_pgn`, e.g. `1. e4 e5 2. Nf3 Nc6 ... 1-0`)
and writes the movetext to that file once the game ends (checkmate,
stalemate, draw, or an interrupted session gets a `*` result), so a
finished game can be reviewed or opened in any standard chess tool.

`chesslite play --load-pgn game.pgn` does the reverse: it parses that
file's movetext (`chesslite/pgn.py`'s `parse_pgn_movetext`, which
strips `[Tag "value"]` headers, `{...}` comments, move-number markers,
and any trailing result token) and replays each SAN move
(`Game.push_san`/`Game.from_pgn`) from the starting position before
play continues interactively or against `--ai` — so a saved game can
be resumed, or an imported PGN from another source can be picked up
and finished out. `push_san` accepts `0-0`/`0-0-0` as well as
`O-O`/`O-O-O`, and tolerates a missing trailing `+`/`#` check marker,
since not every PGN source includes one. A movetext with an illegal
move reports a clean `error: bad PGN in ...` and exits rather than
crashing.

## nanosql

A tiny SQL database engine: a hand-written lexer and recursive-descent
parser for a small SQL subset, a tuple-based table engine, and
single-JSON-file persistence — no external database dependency.

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/nanosql exec mydb.json "CREATE TABLE users (id INT, name TEXT, age INT)"
.venv/bin/nanosql exec mydb.json "INSERT INTO users VALUES (1, 'Ada', 36)"
.venv/bin/nanosql exec mydb.json "SELECT name FROM users WHERE age > 18 ORDER BY age DESC LIMIT 5"
.venv/bin/nanosql shell mydb.json   # interactive prompt, statements end with ';'
```

Supports `CREATE TABLE` (with `INT`/`REAL`/`TEXT` column types),
`INSERT` (with or without an explicit column list), `SELECT` (column
list or `*`, `WHERE` with `=`/`!=`/`<`/`<=`/`>`/`>=`/`LIKE` combined
via `AND`/`OR`, `GROUP BY`, `ORDER BY ASC|DESC`, `LIMIT`),
`UPDATE ... SET ... WHERE`, and `DELETE FROM ... WHERE`. Each `exec`
call loads the whole database file, applies one statement, and saves
it back — good enough for a single-user local database, not concurrent
access. A syntax error or an unknown table/column raises a clean
`error: ...` message and a non-zero exit rather than a traceback.

`WHERE column LIKE 'pattern'` does simple SQL-style pattern matching
against a string column: `%` matches any run of characters (including
none), `_` matches exactly one character, and everything else must
match literally — the whole value has to match the pattern, not just a
substring:

```
.venv/bin/nanosql exec mydb.json "SELECT name FROM users WHERE name LIKE 'A%'"
.venv/bin/nanosql exec mydb.json "SELECT name FROM users WHERE name LIKE '_da'"
```

`SELECT` also supports aggregate functions — `COUNT(*)`, `COUNT(col)`,
`SUM`, `AVG`, `MIN`, `MAX` — optionally grouped with `GROUP BY`:

```
.venv/bin/nanosql exec mydb.json "SELECT COUNT(*) FROM users"
.venv/bin/nanosql exec mydb.json "SELECT department, COUNT(*), AVG(age) FROM users GROUP BY department"
```

A plain column in the `SELECT` list must either be the `GROUP BY`
column or be wrapped in an aggregate function — anything else raises a
clean error, the same way a real SQL engine would reject it. With no
`GROUP BY`, aggregates run over the whole (optionally `WHERE`-filtered)
table as a single group, and `COUNT`/`SUM` over zero matching rows
still return one row (`0`), matching standard SQL rather than
returning no rows at all.

`SELECT` also supports a single inner `JOIN` against another table,
matched on an equality or comparison condition:

```
.venv/bin/nanosql exec mydb.json "CREATE TABLE orders (id INT, user_id INT, item TEXT)"
.venv/bin/nanosql exec mydb.json "INSERT INTO orders VALUES (1, 1, 'Widget')"
.venv/bin/nanosql exec mydb.json "SELECT orders.item, users.name FROM orders JOIN users ON orders.user_id = users.id"
```

Columns can be table-qualified (`orders.item`) anywhere a column is
expected — `SELECT` list, `WHERE`, `GROUP BY`, `ORDER BY` — or left
unqualified when the name only exists in one of the two tables; an
unqualified name that exists in both raises a clean "ambiguous"
error rather than silently picking one. `SELECT *` on a joined query
returns every column from both tables under qualified names
(`orders.id`, `users.id`, ...) since two tables can otherwise share a
column name. Only one `JOIN` per query is supported (no chained
multi-table joins), and it's always an inner join — a row from either
side with no match on the other is simply excluded from the result.

`CREATE INDEX name ON table (column)` builds a hash index (value ->
matching rows) that a plain `WHERE column = value` on that table uses
instead of scanning every row:

```
.venv/bin/nanosql exec mydb.json "CREATE INDEX idx_name ON users (name)"
.venv/bin/nanosql exec mydb.json "SELECT * FROM users WHERE name = 'Ada'"
```

An index is kept in sync automatically on `INSERT`/`UPDATE`/`DELETE`
and persists across `exec` calls (the JSON file records which columns
are indexed; a `shell`/`exec` reload rebuilds the index from the saved
rows). It only accelerates a single top-level `column = value`
comparison — a `!=`/`<`/range condition, an `OR`, or a join still
falls back to a full scan.

`BEGIN`/`COMMIT`/`ROLLBACK` give multiple statements atomicity: nothing
run after `BEGIN` is saved to disk (or visible to a fresh `exec`/`shell`
process) until `COMMIT`, and `ROLLBACK` discards every change made
since `BEGIN`, restoring the exact state as of that point:

```
.venv/bin/nanosql exec mydb.json "BEGIN; UPDATE accounts SET balance = balance - 20 WHERE id = 1; UPDATE accounts SET balance = balance + 20 WHERE id = 2; COMMIT;"
```

A single `exec` call already accepts a `;`-separated script of several
statements, not just one — and a script is atomic even *without* an
explicit `BEGIN`/`COMMIT`: if any statement in it fails, nothing from
that call is saved (the file on disk is untouched), and a script that
ends with a transaction still open is treated as an error (nothing
saves — commit or roll it back explicitly before the call ends,
since there's no way to resume an open transaction across separate
`exec` invocations). In `shell`, an open transaction spans multiple
interactive commands as you'd expect, and exiting the shell with one
still open prints a warning and discards it rather than saving.

Database files are also written crash-safely: `save()` writes the
full JSON to a temp file in the same directory, `fsync`s it, then
`os.replace()`s it into place — so a process killed mid-save can never
leave `mydb.json` half-written or corrupt; you always get either the
old file or the fully-written new one.

`ALTER TABLE table ADD COLUMN name TYPE` and
`ALTER TABLE table DROP COLUMN name` (the `COLUMN` keyword is
optional in both) change a table's schema after creation:

```
.venv/bin/nanosql exec mydb.json "ALTER TABLE users ADD COLUMN email TEXT"
.venv/bin/nanosql exec mydb.json "ALTER TABLE users DROP COLUMN email"
```

Adding a column backfills every existing row with `NULL` for it;
dropping a column removes it from every row and, if it was indexed,
drops the index too. Adding a column that already exists, dropping one
that doesn't, or referencing a dropped column afterward all raise a
clean error rather than corrupting the table.

## procman

A small process supervisor: describe a set of services in a JSON
config file, then have procman start, monitor, and (optionally)
auto-restart them on crash, with per-service logs and a live JSON
status file another process (or a person) can poll.

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/procman validate services.json
.venv/bin/procman run services.json --log-dir logs --status status.json
.venv/bin/procman status status.json
```

A config file looks like:

```json
{
  "services": [
    {"name": "web", "command": ["python3", "server.py"], "autorestart": true, "max_restarts": 5},
    {"name": "worker", "command": ["python3", "worker.py"], "cwd": "/opt/app", "env": {"QUEUE": "jobs"}}
  ]
}
```

`procman run` spawns every service, then polls once per second (tune
with `--interval`) checking whether each one is still alive. A crashed
service with `autorestart` (the default) is respawned automatically,
up to `max_restarts` (default 5) times, after which it's left stopped
rather than restart-looping forever; `autorestart: false` leaves a
crashed service stopped immediately. Each service's stdout/stderr are
captured to `<log-dir>/<name>.log`. `Ctrl+C`/`SIGTERM` triggers a
graceful shutdown: every child is sent `SIGTERM`, then `SIGKILL` after
a timeout if it hasn't exited. `--status` writes a JSON snapshot
(name, running, pid, restart count, last exit code, whether a restart
is pending) after every poll tick and on shutdown, so `procman status
<file>` — or any other process — can check on things without talking
to the supervisor directly.

A service that crashes immediately on every start (a bad command, a
missing dependency) would otherwise be respawned every poll tick,
burning CPU on a tight crash loop. Set `restart_delay` (seconds,
default `0` — respawn immediately, the old behavior) on a service to
wait that long before the first restart, doubling on each further
consecutive crash and capped at 60 seconds:

```json
{"name": "flaky", "command": ["python3", "flaky.py"], "restart_delay": 2.0}
```

A service waiting out its backoff shows `"running": false,
"restart_pending": true` in the status file until the delay elapses
and it respawns.

Services can declare startup dependencies via `depends_on` (a list of
other service names in the same config):

```json
{
  "services": [
    {"name": "db", "command": ["python3", "db.py"]},
    {"name": "cache", "command": ["python3", "cache.py"], "depends_on": ["db"]},
    {"name": "web", "command": ["python3", "server.py"], "depends_on": ["db", "cache"]}
  ]
}
```

`procman` resolves a dependency-respecting start order (a topological
sort) regardless of the order services are listed in the config, and
spawns every service in that order — a service is never spawned before
everything it `depends_on`. Shutdown reverses that order, so a
dependency isn't torn down while something depending on it is still
running. `depends_on` entries can reference services defined later in
the file (forward references are fine); an unknown service name or a
circular dependency (`a` depends on `b` depends on `a`) is rejected at
load time with a clean error from both `procman run` and `procman
validate`, before anything is spawned. `procman validate` also prints
each service's `depends_on` list, if any.

A dependency can also declare a `ready_check`, so its dependents wait
for it to actually be usable, not just spawned:

```json
{
  "services": [
    {
      "name": "db", "command": ["python3", "db.py"],
      "ready_check": {"type": "tcp", "port": 5432, "timeout": 10.0, "interval": 0.2}
    },
    {
      "name": "web", "command": ["python3", "server.py"], "depends_on": ["db"],
      "ready_check": {"type": "command", "command": ["curl", "-fs", "http://localhost:8000/health"]}
    }
  ]
}
```

Two check types: `tcp` (connects to `host`/`port`, default host
`127.0.0.1`) and `command` (runs a command, ready when it exits 0 —
handy for an HTTP health endpoint via `curl`, or any custom check).
`timeout` (default 10s) and `interval` (default 0.2s) control how
long and how often `procman run` polls before giving up. After
spawning a service with a `ready_check`, `start_all` blocks — polling
at `interval` — until the check passes, the service exits on its own
first (a startup crash), or `timeout` elapses; either failure aborts
the whole `run` with a clean error, tearing down every service already
started, since a dependent can't safely start atop a dependency that
never came up. A service with no `ready_check` still only gets the
old ordering guarantee: spawned before its dependents, not confirmed
ready.

Each service's log (`<log-dir>/<name>.log`) otherwise grows without
bound for the life of the config. Set `max_log_bytes` (per service) or
pass `--max-log-bytes` (a default applied to every service that
doesn't set its own) to rotate it to a single `.1` backup once it
reaches that size:

```json
{"name": "web", "command": ["python3", "server.py"], "max_log_bytes": 10485760}
```

Rotation is checked at every spawn (the initial start and every
restart), moving the existing log aside before the fresh one is
opened — procman has no way to make an already-running child reopen
its inherited log file descriptor, so a long-lived service that never
restarts won't rotate mid-run. `procman validate` prints a service's
`max_log_bytes` when set.

`procman run --pid-file PATH` writes its own pid to `PATH` on start and
removes it on clean exit, so another terminal or script can stop a
backgrounded run without knowing its pid in advance:

```
procman run services.json --status status.json --pid-file procman.pid &
procman stop procman.pid
```

`procman stop` sends `SIGTERM` to the pid on record and polls (every
0.1s, up to `--timeout` seconds, default 10) until the process is gone,
mirroring the same graceful-shutdown path `Ctrl+C`/`SIGTERM` already
trigger directly. A missing or malformed pid file, a pid with no
running process, or a process that doesn't exit within the timeout
(e.g. one that's already ignoring `SIGTERM`) all report a clean error
and exit 1 rather than hanging or crashing.

## regexlite

A small regex engine built from scratch: a parser produces an AST,
which is compiled via Thompson's construction into an NFA, matched by
simulating all live NFA states in parallel per input character (Pike's
algorithm) rather than backtracking. This makes matching linear in
`len(pattern) * len(text)` in the worst case, immune to the
catastrophic-backtracking blowup a naive engine hits on patterns like
`(a*)*b` against a long non-matching input.

```
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/regexlite match 'a*b' 'aaab'
.venv/bin/regexlite search '\d+' 'order #4521 shipped'
.venv/bin/regexlite findall '\w+@\w+\.\w+' 'bob@example.com, alice@test.org'
.venv/bin/regexlite grep '^apple' fruit.txt
```

Or as a library:

```python
import regexlite
m = regexlite.search(r'\d+', 'order #4521')
m.group()  # '4521'
regexlite.findall(r'\w+', 'hello world')  # ['hello', 'world']
```

Supported syntax: literal characters, `.` (any character), `*`/`+`/`?`
repetition (and their lazy forms `*?`/`+?`/`??`), `{m}`/`{m,}`/`{m,n}`
bounded repetition (and lazy `{m,n}?`/`{m,}?`), `|` alternation,
`(...)` grouping, `(?:...)` non-capturing grouping, `(?P<name>...)`
named capturing groups, `[...]`/`[^...]` character classes with ranges
(`[a-z0-9]`), `^`/`$` anchors, the shorthand classes `\d`/`\w`/`\s`
(and their negations `\D`/`\W`/`\S`), and capturing groups via `(...)`.
`{m,n}` is desugared in the parser into `m` required copies plus
`n - m` optional (`?`) copies (or a trailing `*` when unbounded), so
it needs no changes to the NFA compiler or matcher; a `{` not followed
by a valid bound is treated as a literal character rather than an
error. There are no backreferences — fundamentally incompatible with
the NFA-simulation approach (they require backtracking, which is
exactly what this engine is built to avoid).

A lazy quantifier (`a*?`, `a+?`, `a??`) prefers the fewest repetitions
that still let the rest of the pattern match, instead of the greedy
default's most; `<.+?>` against `<a><b>` matches just `<a>`, where
greedy `<.+>` would swallow through to the final `>`. This is
implemented at both the compiler and matcher layers: the NFA compiler
swaps which branch of a repetition's `split` state is higher priority
(exit-first for lazy vs. loop-first for greedy), and the matcher keeps
its per-position thread list in that priority order, dropping every
lower-priority thread the moment a higher-priority one reaches
`match` — the standard technique for giving a Thompson-NFA simulation
Perl-style leftmost-priority semantics instead of simply reporting
whichever thread happens to reach `match` at the largest position.

Every `(...)` is a capturing group, numbered 1-up left-to-right by
opening paren; `(?:...)` groups for structure (alternation, repetition)
without allocating a capture number, and `(?P<name>...)` captures under
both a number and a name. Each capturing group's span is tracked
per-NFA-thread as a pair of `save` pseudo-instructions bracketing the
group's compiled fragment — a natural extension of Pike's algorithm
(the same technique RE2 uses): each live thread carries its own
capture-offsets tuple, cloned at each branch point and updated in
place at a `save` instruction, so submatch tracking stays linear-time
along with everything else this engine does. `Match.group(n)`/
`.span(n)`/`.start(n)`/`.end(n)` (n=0 is the whole match, the default;
n may also be a group's name) expose a group's text/offsets,
`Match.groups()` returns every group's text as a tuple, and
`Match.groupdict()` returns `{name: text}` for every named group; an
unmatched group (e.g. the untaken side of `(a)|(b)`, or a `(b)?` that
didn't participate) reports `None`. A group inside a repetition (`(a)+`)
only remembers its last iteration's span, matching Python's own `re`.
A duplicate name, or an unrecognized `(?...)` extension (e.g.
lookaround), raises `RegexSyntaxError` at compile time rather than
silently misbehaving.

`match` anchors at the start of the string but allows a shorter match
(mirroring Python's `re.match`); `fullmatch` requires the whole string
to match; `search` scans for the first (leftmost) match anywhere in
the string; `findall` returns every non-overlapping match, advancing
past zero-width matches by one character to avoid looping forever on
patterns like `a*`.

`sub(pattern, repl, text, count=0)` / `subn(...)` (same, but also
returns the number of replacements made) replace every non-overlapping
match with `repl`, reusing the same zero-width-match advancing rule as
`findall`. `repl` can be a plain string with backreferences — `\1`,
`\2`, ... or `\g<N>` for a specific group number, `\g<name>` for a
named group, `\\` for a literal backslash, `\0`/`\g<0>` for the whole
match — or a callable taking a
`Match` and returning the replacement text for it, mirroring Python's
`re.sub`. A backreference to a group that exists but didn't
participate in the match expands to the empty string; a reference to a
group number that doesn't exist raises `RegexSubError`. `count`
limits the number of replacements (0 means replace all). Available
from the CLI too: `regexlite sub PATTERN REPL STRING [--count N]`.

## autograd

A tiny scalar reverse-mode automatic differentiation engine plus a
small multi-layer perceptron built on top of it — no numpy, no
tensors, no third-party dependency. See `autograd/README.md` for full
details; quick start:

```
pip install -e .
autograd-nn train --dataset xor --epochs 300 --lr 0.5 --verbose
```

Each number in the network is its own `Value` node
(`autograd/engine.py`) that remembers how it was computed; calling
`.backward()` on a loss walks the resulting graph in reverse and
accumulates gradients into every parameter — the same core technique
real frameworks use, just scalar-by-scalar instead of vectorized, so
you can print any intermediate `Value` and see exactly what produced
it. `autograd/nn.py`'s `MLP` composes `Value`-based neurons into
layers; `autograd/train.py` runs full-batch gradient descent;
`autograd/datasets.py` generates three small synthetic datasets (XOR,
two Gaussian blobs, and a ring-around-a-disk) offline via seeded
`random`, so training is fully reproducible with no downloaded data.

## gridsheet

A small spreadsheet engine: cells hold either a literal (a number or
text) or a `=formula` referencing other cells, and changing one cell
automatically recomputes every cell that transitively depends on it —
the same dependency-graph-plus-recalculation model real spreadsheets
use, backed by a plain JSON file rather than a binary format.

```
pip install -e .
gridsheet set budget.json A1 100
gridsheet set budget.json A2 250
gridsheet set budget.json B1 "=SUM(A1:A2)"
gridsheet get budget.json B1   # 350
gridsheet show budget.json     # prints the whole grid
gridsheet shell budget.json    # interactive REPL: "A1 = 5", "show", "get A1"
gridsheet export budget.json budget.csv   # write computed values as CSV
```

Formulas support `+ - * /` with normal precedence, parentheses, cell
references (`A1`), ranges (`A1:A3`), and `SUM`/`AVG`/`MIN`/`MAX`/`COUNT`
over a range or a comma-separated mix of cells and literals, plus
`IF(cond, true_val, false_val)`, `ROUND(value, digits)`, and `ABS(value)`.
Comparisons (`= <> < > <= >=`) evaluate to `1`/`0` (true/false) and are
mainly useful as an `IF` condition, e.g.
`=IF(SUM(A1:A2)>200, ROUND(SUM(A1:A2)/3, 2), 0)`. `IF` only evaluates
its taken branch, so an error in the untaken branch (e.g. a
divide-by-zero that only applies in one case) doesn't propagate — but
both branches still count as dependencies, since either could become
the taken one after a future edit. There's no string-literal syntax,
so a text `IF` branch has to come from a cell reference rather than a
quoted literal. A blank cell reads as `0` in arithmetic; a
divide-by-zero or reference to an unknown function produces an error
value (`#DIV/0!`, `#NAME?`, `#VALUE!`) that propagates through anything
downstream, rather than crashing — the same way a real spreadsheet
shows an error cell instead of halting.

`gridsheet/sheet.py`'s `Sheet` tracks a `depends_on`/`dependents` graph
alongside the cells themselves. Setting a cell only recomputes its
*closure* — itself plus every cell reachable via `dependents` — in
topological order, not the whole sheet, so recalculation stays cheap
as a sheet grows. Before accepting a new formula, `Sheet` walks its
proposed dependencies looking for a path back to the cell being set;
if one exists, the whole change is rejected with a clean
`SheetError("circular reference...")` and nothing is mutated, rather
than silently looping forever or leaving the graph half-rewired.
Loading a saved sheet from JSON doesn't require cells to appear in
dependency order in the file (a forward reference like `B1` naming
`A1` before `A1`'s own entry works fine) — the whole file is parsed
first, then evaluated in one topological pass; a cycle hand-edited
into the JSON is caught the same way, via a short topological order
that couldn't include every cell.

`gridsheet export FILE.json OUT.csv` (also available as `export
OUT.csv` inside the interactive shell) writes the sheet's *computed*
values, not its formulas, as a plain CSV grid — useful for handing a
sheet's results to something that only speaks CSV, e.g. vitalsdash.
An error cell's value (`#DIV/0!`, etc.) is written out as that same
error string, matching what `show`/`get` would already display.

`gridsheet fill FILE.json SRC DEST` (also available as `fill SRC DEST`
inside the shell) copies `SRC`'s content into `DEST` — a single cell
(`B2`) or a range (`B2:B10`) — the same way dragging a spreadsheet
cell's fill handle works. A formula's cell references shift by the
offset between `SRC` and each destination cell (`=A1*10` filled from
`B1` down into `B2` becomes `=A2*10`); prefixing a reference's column
and/or row with `$` locks that part so it doesn't shift
(`=A1+$D$1` filled anywhere still reads the same `D1`). A literal
value is copied unchanged. Filling a reference off the edge of the
grid (column/row below 1) raises a clean `SheetError` rather than
wrapping around or crashing.

## huffc

A small Huffman-coding file compressor: a genuinely different state
shape from every prior build-lane project — a frequency-weighted
binary tree and a bit-packed stream, rather than a graph, an index, a
socket protocol, or a relational store.

```
pip install -e .
huffc compress input.txt input.huf
huffc decompress input.huf output.txt
huffc stats input.txt          # show sizes/ratio without writing a file
```

`huffc/huffman.py` builds a frequency table over the input's raw bytes
(`build_frequencies`), then a Huffman tree via the standard
repeatedly-merge-the-two-least-frequent-nodes algorithm (`build_tree`,
via `heapq`), then walks it to assign each byte a variable-length
bit-string code (`build_codes`) — more frequent bytes get shorter
codes, which is what makes the output smaller for skewed data (plain
English text, or any file with repeated bytes) while random/already-
compressed data barely shrinks or can even grow slightly, the same
tradeoff any Huffman coder has.

A compressed file (`huffc/format.py`) is fully self-contained: a
`HUFC1` magic header, the frequency table itself (so the decoder can
rebuild the *exact* same tree — including canonical tie-breaking by
symbol value when two bytes share a frequency, not by whatever order
they happened to appear in memory, since compress and decompress see
that order differently), and the bit-packed stream. Knowing the total
symbol count from the frequency table lets the decoder stop at exactly
the right point without a separate padding-length field. A single
distinct byte (e.g. a run of the same character) still produces a
valid one-leaf tree with a defined code, and an empty file round-trips
to an empty file. `huffc/bitio.py` provides the `BitWriter`/`BitReader`
helpers used to pack/unpack the bitstream.

`decompress` raises a clean `FormatError` (reported as `error: ...`,
exit 1) on a file that isn't a valid `huffc` blob, rather than
crashing or silently producing garbage.
