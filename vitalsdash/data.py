"""CSV loading for vitalsdash.

Expected format: a header row `timestamp,<metric>,<metric>,...` where
every non-timestamp column is numeric. Rows that fail to parse as
numbers are skipped rather than raising, since hand-appended log
files occasionally pick up a stray malformed line.
"""

import csv


def load_vitals(csv_path):
    """Read a vitals CSV and return (metric_names, records).

    metric_names is the ordered list of non-timestamp columns.
    records is a list of dicts: {"timestamp": str, metric: float, ...}
    """
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "timestamp" not in reader.fieldnames:
            raise ValueError("csv must have a 'timestamp' column")
        metric_names = [name for name in reader.fieldnames if name != "timestamp"]

        records = []
        for row in reader:
            try:
                record = {"timestamp": row["timestamp"]}
                for name in metric_names:
                    record[name] = float(row[name])
            except (TypeError, ValueError):
                continue
            records.append(record)

    return metric_names, records
