"""Minimal HTTP server for vitalsdash: one JSON endpoint, one HTML page.

Uses only the standard library (http.server) so it can run on
hardware with no network access to fetch dependencies, and serves a
single self-contained HTML page that draws its own SVG line charts —
no CDN scripts, no build step.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .data import load_vitals

PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>vitalsdash</title>
<style>
  body {{ font-family: monospace; background: #111; color: #eee; margin: 2rem; }}
  h1 {{ font-size: 1.1rem; color: #8fd; }}
  .chart {{ margin-bottom: 2rem; }}
  .chart h2 {{ font-size: 0.9rem; color: #aaa; margin: 0 0 0.3rem 0; }}
  svg {{ background: #1a1a1a; border: 1px solid #333; }}
  polyline {{ fill: none; stroke: #8fd; stroke-width: 1.5; }}
  circle.over {{ fill: #f66; }}
  circle.under {{ fill: #8fd; }}
  line.threshold {{ stroke: #f66; stroke-width: 1; stroke-dasharray: 4 3; }}
  text {{ fill: #888; font-size: 9px; }}
  text.threshold-label {{ fill: #f66; }}
  h2.breached {{ color: #f66; }}
</style>
</head>
<body>
<h1>vitalsdash — {source}</h1>
<div id="charts"></div>
<script>
async function main() {{
  const res = await fetch('/api/vitals');
  const data = await res.json();
  const thresholds = data.thresholds || {{}};
  const container = document.getElementById('charts');
  const W = 700, H = 140, PAD = 20;

  for (const metric of data.metrics) {{
    const values = data.records.map(r => r[metric]);
    const threshold = thresholds[metric];
    const min = Math.min(...values, ...(threshold !== undefined ? [threshold] : []));
    const max = Math.max(...values, ...(threshold !== undefined ? [threshold] : []));
    const range = (max - min) || 1;
    const toXY = (v, i) => {{
      const x = PAD + (i / Math.max(values.length - 1, 1)) * (W - 2 * PAD);
      const y = H - PAD - ((v - min) / range) * (H - 2 * PAD);
      return [x, y];
    }};

    const points = values.map((v, i) => toXY(v, i).map(n => n.toFixed(1)).join(',')).join(' ');
    const latest = values[values.length - 1];
    const breached = threshold !== undefined && latest > threshold;

    let thresholdSvg = '';
    if (threshold !== undefined) {{
      const [, ty] = toXY(threshold, 0);
      thresholdSvg = `<line class="threshold" x1="${{PAD}}" y1="${{ty.toFixed(1)}}" x2="${{W - PAD}}" y2="${{ty.toFixed(1)}}" />
        <text class="threshold-label" x="${{W - PAD - 60}}" y="${{(ty - 3).toFixed(1)}}">threshold ${{threshold}}</text>`;
    }}

    const circles = values.map((v, i) => {{
      const [x, y] = toXY(v, i);
      const cls = threshold !== undefined && v > threshold ? 'over' : 'under';
      return `<circle class="${{cls}}" cx="${{x.toFixed(1)}}" cy="${{y.toFixed(1)}}" r="1.8" />`;
    }}).join('');

    const div = document.createElement('div');
    div.className = 'chart';
    div.innerHTML = `
      <h2 class="${{breached ? 'breached' : ''}}">${{metric}} (min ${{min.toFixed(2)}}, max ${{max.toFixed(2)}}, latest ${{latest}}${{breached ? ' — over threshold' : ''}})</h2>
      <svg width="${{W}}" height="${{H}}">
        ${{thresholdSvg}}
        <polyline points="${{points}}" />
        ${{circles}}
        <text x="${{PAD}}" y="${{H - 4}}">${{data.records[0] ? data.records[0].timestamp : ''}}</text>
        <text x="${{W - 140}}" y="${{H - 4}}">${{data.records.length ? data.records[data.records.length - 1].timestamp : ''}}</text>
      </svg>`;
    container.appendChild(div);
  }}
}}
main();
</script>
</body>
</html>
"""


def _make_handler(csv_path, thresholds):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # keep stdout quiet on a resource-constrained host

        def do_GET(self):
            if self.path == "/api/vitals":
                metric_names, records = load_vitals(csv_path)
                body = json.dumps(
                    {"metrics": metric_names, "records": records, "thresholds": thresholds}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/":
                body = PAGE_TEMPLATE.format(source=csv_path).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

    return Handler


def make_server(csv_path, host="127.0.0.1", port=8099, thresholds=None):
    """Build (but do not start) a ThreadingHTTPServer serving csv_path.

    thresholds, if given, maps metric name -> a value above which the
    dashboard highlights that metric's chart (red points/heading, a
    dashed reference line).
    """
    return ThreadingHTTPServer((host, port), _make_handler(csv_path, thresholds or {}))
