"""JSON persistence for a Sheet: {"A1": "5", "B1": "=A1*2"}."""
import json

from gridsheet.sheet import Sheet


def save_sheet(sheet, path):
    with open(path, "w") as f:
        json.dump(sheet.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")


def load_sheet(path):
    with open(path) as f:
        data = json.load(f)
    return Sheet.from_dict(data)
