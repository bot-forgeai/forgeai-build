"""JSON persistence for a Sheet: {"A1": "5", "B1": "=A1*2"}."""
import csv
import json

from gridsheet.refs import num_to_col
from gridsheet.sheet import Sheet


def save_sheet(sheet, path):
    with open(path, "w") as f:
        json.dump(sheet.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")


def load_sheet(path):
    with open(path) as f:
        data = json.load(f)
    return Sheet.from_dict(data)


def _csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return str(value)
    return str(value)


def export_csv(sheet, path):
    """Write the sheet's computed values (not formulas) as a plain grid of cells."""
    max_c, max_r = sheet.bounds()
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        for r in range(1, max_r + 1):
            row = [_csv_cell(sheet.get_value(f"{num_to_col(c)}{r}")) for c in range(1, max_c + 1)]
            writer.writerow(row)
