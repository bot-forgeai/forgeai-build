"""vitalsdash — a tiny standalone dashboard for time-series metrics CSVs.

Point it at any CSV with a `timestamp` column plus numeric metric
columns (the format tools/pi_vitals.py on the ForgeAI Pi produces is
one example) and it serves a local web page charting each metric over
time, with no external dependencies or CDN fetches.
"""

from .data import load_vitals
from .server import make_server

__all__ = ["load_vitals", "make_server"]
