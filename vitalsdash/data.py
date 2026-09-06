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


def _is_float(value):
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


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
