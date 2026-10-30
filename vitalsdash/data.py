"""CSV loading for vitalsdash.

Expected format: a header row `timestamp,<column>,<column>,...`.
Non-timestamp columns that never parse as numbers anywhere in the
file (e.g. a `boot_id` UUID column) are treated as metadata and left
out of the charted metrics, rather than causing every row to be
dropped. Among the remaining numeric columns, individual rows that
fail to parse are skipped rather than raising, since hand-appended
log files occasionally pick up a stray malformed line.
"""

import csv
import math
import statistics
from datetime import datetime, timedelta


def _is_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def load_vitals(csv_path):
    """Read a vitals CSV and return (metric_names, records).

    metric_names is the ordered list of non-timestamp columns that
    contain at least one numeric value. records is a list of dicts:
    {"timestamp": str, metric: float, ...}
    """
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "timestamp" not in reader.fieldnames:
            raise ValueError("csv must have a 'timestamp' column")
        candidate_names = [name for name in reader.fieldnames if name != "timestamp"]
        rows = list(reader)

    metric_names = [
        name for name in candidate_names
        if any(_is_float(row.get(name)) for row in rows)
    ]

    records = []
    for row in rows:
        if not all(_is_float(row.get(name)) for name in metric_names):
            continue
        record = {"timestamp": row["timestamp"]}
        for name in metric_names:
            record[name] = float(row[name])
        records.append(record)

    return metric_names, records


def load_groups(csv_path, group_by=None):
    """Group numeric metrics by a non-numeric column, if there's one to use.

    disk-writes.csv has a `boot_id` column: a counter that resets each
    boot, so a line-over-time chart is misleading (it looks like a
    sawtooth rather than showing per-boot totals). This reads the same
    CSV and returns, for each metric, the max value seen per boot_id
    (the counter's peak within that boot approximates its total) in
    the order boots first appear.

    group_by, if given, names the column to group by explicitly — use
    this when a CSV has more than one non-numeric column and the
    single-column auto-detect below can't pick one unambiguously.
    Otherwise, if the file has exactly one non-numeric column, that
    column is used automatically.

    Returns (group_column, group_labels, {metric: [max_per_group]}).
    If group_by isn't a column in the file, or auto-detect finds zero
    or more than one non-numeric column, there is no unambiguous thing
    to group by, so this returns (None, [], {}).
    """
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "timestamp" not in reader.fieldnames:
            raise ValueError("csv must have a 'timestamp' column")
        candidate_names = [name for name in reader.fieldnames if name != "timestamp"]
        rows = list(reader)

    metric_names = [
        name for name in candidate_names
        if any(_is_float(row.get(name)) for row in rows)
    ]
    group_names = [name for name in candidate_names if name not in metric_names]

    if group_by is not None:
        if group_by not in candidate_names:
            return None, [], {}
        group_column = group_by
        metric_names = [name for name in metric_names if name != group_by]
    elif len(group_names) == 1:
        group_column = group_names[0]
    else:
        return None, [], {}

    order = []
    maxima = {}
    for row in rows:
        gval = row.get(group_column)
        if not gval:
            continue
        if gval not in maxima:
            maxima[gval] = {}
            order.append(gval)
        for name in metric_names:
            if _is_float(row.get(name)):
                v = float(row[name])
                if name not in maxima[gval] or v > maxima[gval][name]:
                    maxima[gval][name] = v

    per_metric = {
        name: [maxima[g].get(name) for g in order] for name in metric_names
    }
    return group_column, order, per_metric


def find_gaps(records, factor=3.0):
    """Find stretches where logging stalled.

    A gap is a pair of consecutive records whose timestamps are more than
    `factor` times the median interval apart. Returns a list of
    {"start": str, "end": str, "hours": float}. Needs at least 3 parseable
    ISO timestamps (to have a meaningful median); otherwise returns [].
    """
    stamps = []
    for r in records:
        try:
            stamps.append((r["timestamp"], datetime.fromisoformat(r["timestamp"])))
        except ValueError:
            continue
    if len(stamps) < 3:
        return []
    deltas = [(b[1] - a[1]).total_seconds() for a, b in zip(stamps, stamps[1:])]
    median = statistics.median(deltas)
    if median <= 0:
        return []
    return [
        {"start": a[0], "end": b[0], "hours": round(d / 3600, 2)}
        for (a, b), d in zip(zip(stamps, stamps[1:]), deltas)
        if d > factor * median
    ]


def freshness(records, now=None):
    """How current the log is: newest sample, its age, and logging gaps.

    Returns {"newest": str, "age_hours": float, "gaps": count,
    "longest_gap_hours": float}, or None if no timestamp parses. `now` is a
    naive datetime (default: local time now), matching the CSV's stamps.
    """
    stamps = []
    for r in records:
        try:
            stamps.append(datetime.fromisoformat(r["timestamp"]))
        except ValueError:
            continue
    if not stamps:
        return None
    newest = max(stamps)
    gaps = find_gaps(records)
    return {
        "newest": newest.isoformat(),
        "age_hours": round(((now or datetime.now()) - newest).total_seconds() / 3600, 2),
        "gaps": len(gaps),
        "longest_gap_hours": max((g["hours"] for g in gaps), default=0.0),
    }


def filter_last_days(records, days):
    """Keep records within `days` of the newest parseable timestamp.

    Records with unparseable timestamps are kept, so a stray bad row
    doesn't silently change the window. days=None returns records as-is.
    """
    if days is None:
        return records
    parsed = []
    for r in records:
        try:
            parsed.append(datetime.fromisoformat(r["timestamp"]))
        except ValueError:
            parsed.append(None)
    stamps = [t for t in parsed if t is not None]
    if not stamps:
        return records
    cutoff = max(stamps) - timedelta(days=days)
    return [r for r, t in zip(records, parsed) if t is None or t >= cutoff]


def to_rate(records, metrics):
    """Turn cumulative counters into per-hour rates.

    For each metric in `metrics`, the value becomes (delta / hours since
    the previous record) and the key is renamed `<metric>/h`. A counter
    that reset (negative delta, e.g. across a reboot) or two records
    with no time between them produce no point, so the record is
    dropped rather than charted as a spike. The first record has no
    predecessor and is dropped too.
    """
    if not metrics:
        return records
    out = []
    prev = None
    for rec in records:
        t = datetime.fromisoformat(rec["timestamp"])
        if prev is not None:
            hours = (t - prev[0]).total_seconds() / 3600
            new = {"timestamp": rec["timestamp"]}
            ok = hours > 0
            for k, v in rec.items():
                if k == "timestamp":
                    continue
                if k in metrics:
                    d = v - prev[1][k]
                    if d < 0:
                        ok = False
                    elif ok:
                        new[k + "/h"] = d / hours
                else:
                    new[k] = v
            if ok:
                out.append(new)
        prev = (t, rec)
    return out


def percentile(values, pct):
    """Linear-interpolated percentile (pct in 0..100) of a non-empty list."""
    ordered = sorted(values)
    pos = (len(ordered) - 1) * pct / 100
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def trend_per_day(stamped):
    """Least-squares slope, in value units per day, of (datetime, value) pairs.

    None when there are fewer than two points or all share one timestamp.
    """
    if len(stamped) < 2:
        return None
    t0 = stamped[0][0]
    xs = [(t - t0).total_seconds() / 86400 for t, _ in stamped]
    ys = [v for _, v in stamped]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    var = sum((x - mx) ** 2 for x in xs)
    if var == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var


def breach_history(points, limit, below=False):
    """How often (timestamp, value) points crossed `limit`, not just the latest one.

    Returns {"n": breaching samples, "longest_run": longest consecutive
    streak of them, "last": timestamp of the most recent breach or None}.
    """
    n = run = longest = 0
    last = None
    for stamp, value in points:
        if (value < limit) if below else (value > limit):
            n += 1
            run += 1
            longest = max(longest, run)
            last = stamp
        else:
            run = 0
    return {"n": n, "longest_run": longest, "last": last}


def summarize(metric_names, records, thresholds=None, below=()):
    """Per-metric stats for a one-shot text report.

    Returns a list of dicts: {"metric", "n", "min", "mean", "max",
    "p95", "trend_per_day", "latest", "breached"}. p95 is the 95th
    percentile; trend_per_day is the least-squares slope per day over
    records with parseable timestamps (None if under two points). A metric breaches when its latest value is
    above its threshold, or below it if the metric is listed in `below`
    (same rule the dashboard uses to highlight a chart). Metrics with no
    records are skipped.
    """
    thresholds = thresholds or {}
    rows = []
    for name in metric_names:
        values = [r[name] for r in records if name in r]
        if not values:
            continue
        latest = values[-1]
        limit = thresholds.get(name)
        if limit is None:
            breached = False
        elif name in below:
            breached = latest < limit
        else:
            breached = latest > limit
        history = None
        if limit is not None:
            history = breach_history(
                [(r["timestamp"], r[name]) for r in records if name in r], limit, name in below)
        stamped = []
        for r in records:
            if name in r:
                try:
                    stamped.append((datetime.fromisoformat(r["timestamp"]), r[name]))
                except ValueError:
                    pass
        rows.append({
            "metric": name,
            "n": len(values),
            "min": min(values),
            "mean": sum(values) / len(values),
            "max": max(values),
            "p95": percentile(values, 95),
            "trend_per_day": trend_per_day(stamped),
            "latest": latest,
            "breached": breached,
            "breach_n": history and history["n"],
            "breach_longest_run": history and history["longest_run"],
            "last_breach": history and history["last"],
        })
    return rows
