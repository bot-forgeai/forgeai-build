"""Minimal HTTP server for vitalsdash: one JSON endpoint, one HTML page.

Uses only the standard library (http.server) so it can run on
hardware with no network access to fetch dependencies, and serves a
single self-contained HTML page that draws its own SVG line charts —
no CDN scripts, no build step.
"""

import json
import os
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
  svg {{ background: #1a1a1a; border: 1px solid #333; margin-right: 0.75rem; }}
  polyline {{ fill: none; stroke: #8fd; stroke-width: 1.5; }}
  circle.over {{ fill: #f66; }}
  circle.under {{ fill: #8fd; }}
  line.threshold {{ stroke: #f66; stroke-width: 1; stroke-dasharray: 4 3; }}
  text {{ fill: #888; font-size: 9px; }}
  text.threshold-label {{ fill: #f66; }}
  rect.hist-bar {{ fill: #8fd; }}
  .charts-row {{ display: flex; flex-wrap: wrap; align-items: flex-end; }}
  .series-block {{ margin-bottom: 0.5rem; }}
  .series-label {{ font-size: 0.8rem; color: #888; margin: 0 0 0.2rem 0; }}
  .series-label.breached {{ color: #f66; }}
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
  const HIST_W = 260, HIST_H = 140, HIST_PAD = 20, HIST_BINS = 10;

  function chartRow(label, values, threshold) {{
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

    return `
      <div class="series-block">
        <h3 class="series-label ${{breached ? 'breached' : ''}}">${{label}} (min ${{min.toFixed(2)}}, max ${{max.toFixed(2)}}, latest ${{latest}}${{breached ? ' — over threshold' : ''}})</h3>
        <div class="charts-row">
          <svg width="${{W}}" height="${{H}}">
            ${{thresholdSvg}}
            <polyline points="${{points}}" />
            ${{circles}}
          </svg>
          ${{histogramSvg(values)}}
        </div>
      </div>`;
  }}

  function histogramSvg(values) {{
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = (max - min) || 1;
    const binWidth = range / HIST_BINS;
    const counts = new Array(HIST_BINS).fill(0);
    for (const v of values) {{
      const idx = Math.min(HIST_BINS - 1, Math.floor((v - min) / binWidth));
      counts[idx]++;
    }}
    const maxCount = Math.max(...counts, 1);
    const plotW = HIST_W - 2 * HIST_PAD;
    const plotH = HIST_H - 2 * HIST_PAD;
    const slot = plotW / HIST_BINS;
    const barW = Math.max(slot - 2, 1);
    const bars = counts.map((c, i) => {{
      const barH = (c / maxCount) * plotH;
      const x = HIST_PAD + i * slot + 1;
      const y = HIST_H - HIST_PAD - barH;
      return `<rect class="hist-bar" x="${{x.toFixed(1)}}" y="${{y.toFixed(1)}}" width="${{barW.toFixed(1)}}" height="${{barH.toFixed(1)}}" rx="2" />`;
    }}).join('');
    return `<svg width="${{HIST_W}}" height="${{HIST_H}}">
        ${{bars}}
        <text x="${{HIST_PAD}}" y="${{HIST_H - 4}}">${{min.toFixed(1)}}</text>
        <text x="${{HIST_W - HIST_PAD - 40}}" y="${{HIST_H - 4}}">${{max.toFixed(1)}}</text>
      </svg>`;
  }}

  const series = data.series || [{{label: data.source || '', metrics: data.metrics, records: data.records}}];
  const comparing = series.length > 1;
  const metricOrder = [];
  for (const s of series) {{
    for (const m of s.metrics) {{
      if (!metricOrder.includes(m)) metricOrder.push(m);
    }}
  }}

  for (const metric of metricOrder) {{
    const div = document.createElement('div');
    div.className = 'chart';
    let inner = `<h2>${{metric}}</h2>`;
    for (const s of series) {{
      if (!s.metrics.includes(metric)) continue;
      const values = s.records.map(r => r[metric]);
      const threshold = thresholds[metric];
      const label = comparing ? s.label : `${{s.records[0] ? s.records[0].timestamp : ''}} — ${{s.records.length ? s.records[s.records.length - 1].timestamp : ''}}`;
      inner += chartRow(label, values, threshold);
    }}
    div.innerHTML = inner;
    container.appendChild(div);
  }}
}}
main();
</script>
</body>
</html>
"""


def _make_handler(csv_path, thresholds, compare_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # keep stdout quiet on a resource-constrained host

        def do_GET(self):
            if self.path == "/api/vitals":
                metric_names, records = load_vitals(csv_path)
                series = [
                    {"label": os.path.basename(csv_path), "metrics": metric_names, "records": records}
                ]
                if compare_path:
                    c_metrics, c_records = load_vitals(compare_path)
                    series.append(
                        {"label": os.path.basename(compare_path), "metrics": c_metrics, "records": c_records}
                    )
                body = json.dumps(
                    {
                        "metrics": metric_names,
                        "records": records,
                        "thresholds": thresholds,
                        "series": series,
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/":
                source = csv_path if not compare_path else f"{csv_path} vs {compare_path}"
                body = PAGE_TEMPLATE.format(source=source).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

    return Handler


def make_server(csv_path, host="127.0.0.1", port=8099, thresholds=None, compare_path=None):
    """Build (but do not start) a ThreadingHTTPServer serving csv_path.

    thresholds, if given, maps metric name -> a value above which the
    dashboard highlights that metric's chart (red points/heading, a
    dashed reference line). compare_path, if given, is a second CSV
    whose charts render alongside csv_path's for each shared metric,
    for eyeballing two boots/runs/machines side by side.
    """
    return ThreadingHTTPServer(
        (host, port), _make_handler(csv_path, thresholds or {}, compare_path)
    )
