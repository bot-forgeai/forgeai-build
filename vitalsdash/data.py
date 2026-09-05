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
