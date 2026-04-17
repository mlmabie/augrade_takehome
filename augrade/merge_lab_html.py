#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Dict

from . import dataset as _ds
from .merge import FAMILY_LABELS  # re-exported for backwards compatibility  # noqa: F401


def fmt_int(value: int) -> str:
    return f"{value:,}"


def fmt_float(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def build_dataset(input_dxf: Path, snap_tolerance: float, extraction=None) -> Dict[str, object]:
    """Build the merge-lab JSON payload embedded in merge_lab.html.

    Thin wrapper over ``augrade.dataset.merge_lab_payload`` so existing callers
    (notably ``run_hitl_pipeline``) keep working while the compute layer lives
    in the augrade package.
    """
    analysis = _ds.build(input_dxf, snap_tolerance, with_merge=True, extraction=extraction)
    return _ds.merge_lab_payload(analysis)


def build_html(dataset: Dict[str, object]) -> str:
    dataset_json = json.dumps(dataset, separators=(",", ":")).replace("</script>", "<\\/script>")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Merge Lab</title>
  <style>
    :root {{
      --bg: #f4efe4;
      --panel: rgba(255,255,255,0.86);
      --ink: #151515;
      --muted: #666;
      --line: rgba(32,32,32,0.10);
      --shadow: 0 22px 60px rgba(10, 10, 10, 0.12);
      --radius: 22px;
      font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(255,255,255,0.7), transparent 36%),
        linear-gradient(180deg, #f5eee2 0%, #e9ece7 100%);
    }}
    .shell {{
      width: min(98vw, 2200px);
      max-width: 2200px;
      margin: 0 auto;
      padding: 18px 14px 40px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 18px;
      margin-bottom: 18px;
    }}
    .panel {{
      background: var(--panel);
      backdrop-filter: blur(12px);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }}
    .hero-copy {{
      padding: 26px;
      position: relative;
      overflow: hidden;
    }}
    .hero-copy::after {{
      content: "";
      position: absolute;
      right: -60px;
      top: -80px;
      width: 220px;
      height: 220px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(47,91,255,0.13), transparent 70%);
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 2.55rem;
      line-height: 0.95;
      letter-spacing: -0.03em;
    }}
    h2 {{
      margin: 0 0 8px;
      font-size: 1.25rem;
      letter-spacing: -0.02em;
    }}
    h3 {{
      margin: 0 0 8px;
      font-size: 1.0rem;
    }}
    p {{
      margin: 10px 0;
      color: var(--muted);
      line-height: 1.45;
    }}
    .hero-image {{
      padding: 16px;
    }}
    .hero-image img {{
      display: block;
      width: 100%;
      max-height: 240px;
      object-fit: contain;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: white;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 285px minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }}
    .sidebar {{
      position: sticky;
      top: 14px;
      padding: 18px;
    }}
    .main {{
      display: grid;
      gap: 14px;
    }}
    .workspace-grid {{
      display: grid;
      grid-template-columns: 1.15fr 1fr;
      gap: 16px;
      align-items: stretch;
    }}
    .candidate-pairs-panel {{
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}
    .candidate-pairs-panel h2,
    .candidate-pairs-panel > .note,
    .candidate-pairs-panel > .button-row {{
      flex: 0 0 auto;
    }}
    .candidate-pairs-panel .list-shell.tall {{
      flex: 1 1 auto;
      min-height: 18rem;
      max-height: none;
      overflow: auto;
    }}
    .right-stack {{
      display: grid;
      gap: 16px;
      align-content: start;
    }}
    .inspection-grid {{
      display: grid;
      grid-template-columns: 0.9fr 0.9fr 1.2fr;
      gap: 12px;
      align-items: start;
    }}
    .provenance-grid {{
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 16px;
    }}
    .stack {{
      display: grid;
      gap: 12px;
    }}
    .sidebar .stack > div + div {{
      margin-top: 4px;
      padding-top: 14px;
      border-top: 1px solid var(--line);
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0,1fr));
      gap: 10px;
      align-items: stretch;
    }}
    .metric {{
      padding: 12px 14px;
      border-radius: 18px;
      background: rgba(255,255,255,0.7);
      border: 1px solid var(--line);
      position: relative;
      overflow: hidden;
    }}
    .metric::before {{
      content: "";
      position: absolute;
      left: 0;
      top: 0;
      width: 100%;
      height: 3px;
      background: var(--accent, #111);
    }}
    .metric .label {{
      color: var(--muted);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .metric .value {{
      font-size: 1.55rem;
      margin-top: 5px;
      font-weight: 700;
      letter-spacing: -0.03em;
    }}
    .metric .detail {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 0.9rem;
      line-height: 1.35;
      min-height: 2.6em;
    }}
    label {{
      display: block;
      font-size: 0.86rem;
      color: #333;
      margin: 8px 0 4px;
      font-weight: 600;
    }}
    select, input[type="range"], input[type="number"], button {{
      width: 100%;
    }}
    select, input[type="number"] {{
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.92);
      font: inherit;
    }}
    input[type="range"] {{
      accent-color: #2f5bff;
    }}
    .slider-row {{
      display: grid;
      grid-template-columns: 1fr auto;
      align-items: center;
      gap: 10px;
    }}
    .slider-value {{
      min-width: 56px;
      text-align: right;
      color: var(--muted);
      font-size: 0.84rem;
      font-variant-numeric: tabular-nums;
    }}
    .button-row {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0,1fr));
      gap: 8px;
      margin-top: 8px;
    }}
    .sidebar .button-row {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    button {{
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.92);
      font: inherit;
      cursor: pointer;
    }}
    .sidebar button {{
      font-size: 0.8rem;
      padding: 9px 10px;
      white-space: nowrap;
    }}
    button.primary {{
      background: #151515;
      color: white;
    }}
    button.good {{
      background: #1b9e5a;
      color: white;
    }}
    button.bad {{
      background: #d9342b;
      color: white;
    }}
    .section {{
      padding: 16px;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 18px;
    }}
    .three-col {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0,1fr));
      gap: 12px;
    }}
    .list-shell {{
      max-height: 360px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255,255,255,0.75);
    }}
    .list-shell.tall {{
      max-height: 640px;
    }}
    .selected-toolbar {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 14px;
      align-items: start;
    }}
    .selected-toolbar h2 {{
      margin: 0 0 6px;
    }}
    .selected-actions {{
      margin-top: 0;
      grid-template-columns: repeat(3, minmax(0,1fr));
    }}
    .selected-bar {{
      margin: 0;
      color: #222;
      font-size: 0.88rem;
      line-height: 1.42;
      font-variant-numeric: tabular-nums;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .compact-note {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.35;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.92rem;
    }}
    th, td {{
      text-align: left;
      padding: 10px 10px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{
      position: sticky;
      top: 0;
      background: rgba(251,251,253,0.96);
      font-size: 0.78rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    tr.active {{
      background: rgba(47,91,255,0.08);
    }}
    .chip {{
      display: inline-block;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 0.76rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.75);
    }}
    .chip.accepted {{ background: rgba(27,158,90,0.12); color: #165f3b; }}
    .chip.review {{ background: rgba(239,171,59,0.16); color: #825400; }}
    .chip.rejected {{ background: rgba(217,52,43,0.12); color: #8f221a; }}
    .chip.labeled-pos {{ background: rgba(27,158,90,0.16); }}
    .chip.labeled-neg {{ background: rgba(217,52,43,0.16); }}
    .preview-wrap {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }}
    .svg-card {{
      border-radius: 18px;
      overflow: hidden;
      border: 1px solid var(--line);
      background: white;
      min-height: 380px;
    }}
    svg.viewer {{
      width: 100%;
      height: auto;
      display: block;
      background: linear-gradient(180deg, #fff 0%, #fbfbfc 100%);
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    .detail-card {{
      padding: 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.72);
    }}
    .detail-card h3 {{
      font-size: 0.88rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 10px;
      min-height: 2.5em;
      line-height: 1.2;
      display: flex;
      align-items: flex-end;
    }}
    dl {{
      margin: 0;
      display: grid;
      grid-template-columns: max-content minmax(0, 1fr);
      gap: 8px 14px;
      font-size: 0.9rem;
      align-items: start;
    }}
    dt {{ color: var(--muted); white-space: nowrap; }}
    dd {{ margin: 0; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; text-align: right; }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: rgba(255,255,255,0.78);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      font-size: 0.82rem;
      line-height: 1.32;
      overflow: auto;
      max-height: 280px;
    }}
    .note {{
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.45;
    }}
    .mini {{
      font-size: 0.82rem;
      color: var(--muted);
    }}
    @media (max-width: 1240px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .sidebar {{
        position: relative;
        top: 0;
      }}
    }}
    @media (max-width: 1100px) {{
      .hero, .two-col, .three-col, .summary-grid, .detail-grid, .selected-toolbar, .workspace-grid, .inspection-grid, .provenance-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="panel hero-copy">
        <h1>Merge Lab</h1>
        <p>This is an expert-in-the-loop interface for normalization and merge tuning. It exposes candidate pair metrics, lets you move hard gates and scoring weights directly, and shows the structural consequence of those choices as accepted edges and merged components.</p>
        <p>It also includes a small associative-memory layer: mark a few clean positives and negatives, then use a Hopfield-like memory margin to bias ranking with very little labeled data.</p>
        <p class="mini" id="metaLine"></p>
      </div>
      <div class="panel hero-image">
        <img src="extracted_overlay.svg" alt="Full extraction overlay">
      </div>
    </section>

    <div class="layout">
      <aside class="panel sidebar">
        <div class="stack">
          <div>
            <label for="familySelect">Family</label>
            <select id="familySelect"></select>
            <p class="mini" id="familyNote"></p>
          </div>

          <div>
            <h2>Hard Gates</h2>
            <label>Max Boundary Gap</label>
            <div class="slider-row"><input id="max_boundary_gap" type="range" min="0" max="120" step="1"><div class="slider-value" id="max_boundary_gap_value"></div></div>
            <label>Max Angle Diff</label>
            <div class="slider-row"><input id="max_angle_diff" type="range" min="0" max="120" step="1"><div class="slider-value" id="max_angle_diff_value"></div></div>
            <label>Max Thickness Rel Diff</label>
            <div class="slider-row"><input id="max_thickness_rel" type="range" min="0" max="3" step="0.05"><div class="slider-value" id="max_thickness_rel_value"></div></div>
            <label>Max Area Ratio</label>
            <div class="slider-row"><input id="max_area_ratio" type="range" min="1" max="12" step="0.1"><div class="slider-value" id="max_area_ratio_value"></div></div>
            <label>Max Major Gap / Scale</label>
            <div class="slider-row"><input id="max_gap_major_norm" type="range" min="0" max="12" step="0.1"><div class="slider-value" id="max_gap_major_norm_value"></div></div>
            <label>Max Minor Gap / Scale</label>
            <div class="slider-row"><input id="max_gap_minor_norm" type="range" min="0" max="4" step="0.05"><div class="slider-value" id="max_gap_minor_norm_value"></div></div>
            <label>Min Major Overlap</label>
            <div class="slider-row"><input id="min_overlap_major" type="range" min="0" max="1" step="0.02"><div class="slider-value" id="min_overlap_major_value"></div></div>
            <label>Min Minor Overlap</label>
            <div class="slider-row"><input id="min_overlap_minor" type="range" min="0" max="1" step="0.02"><div class="slider-value" id="min_overlap_minor_value"></div></div>
          </div>

          <div>
            <h2>Score Weights</h2>
            <label>Boundary Gap Weight</label>
            <div class="slider-row"><input id="w_gap" type="range" min="0" max="3" step="0.05"><div class="slider-value" id="w_gap_value"></div></div>
            <label>Angle Weight</label>
            <div class="slider-row"><input id="w_angle" type="range" min="0" max="3" step="0.05"><div class="slider-value" id="w_angle_value"></div></div>
            <label>Thickness Weight</label>
            <div class="slider-row"><input id="w_thickness" type="range" min="0" max="3" step="0.05"><div class="slider-value" id="w_thickness_value"></div></div>
            <label>Continuity Weight</label>
            <div class="slider-row"><input id="w_continuity" type="range" min="0" max="3" step="0.05"><div class="slider-value" id="w_continuity_value"></div></div>
            <label>Alignment Weight</label>
            <div class="slider-row"><input id="w_alignment" type="range" min="0" max="3" step="0.05"><div class="slider-value" id="w_alignment_value"></div></div>
            <label>IoU Weight</label>
            <div class="slider-row"><input id="w_iou" type="range" min="0" max="3" step="0.05"><div class="slider-value" id="w_iou_value"></div></div>
            <label>Layer Weight</label>
            <div class="slider-row"><input id="w_layer" type="range" min="0" max="3" step="0.05"><div class="slider-value" id="w_layer_value"></div></div>
            <label>Score Threshold</label>
            <div class="slider-row"><input id="score_threshold" type="range" min="-1" max="5" step="0.05"><div class="slider-value" id="score_threshold_value"></div></div>
          </div>

          <div>
            <h2>Memory Layer</h2>
            <label>Hopfield Beta</label>
            <div class="slider-row"><input id="memory_beta" type="range" min="1" max="20" step="0.5"><div class="slider-value" id="memory_beta_value"></div></div>
            <label>Memory Weight</label>
            <div class="slider-row"><input id="w_memory" type="range" min="0" max="3" step="0.05"><div class="slider-value" id="w_memory_value"></div></div>
            <div class="button-row">
              <button id="resetPreset" class="primary" title="Reset gates and weights to the family preset">Reset preset</button>
              <button id="exportLabels" title="Download labels JSON">Export labels</button>
              <button id="importLabels" title="Import labels from JSON">Import labels</button>
            </div>
            <div class="button-row">
              <button id="exportAccepted" title="Download accepted merge edges as JSON">Export merge</button>
              <button id="clearLabels" title="Clear locally stored labels">Clear labels</button>
              <button id="downloadTemplate" title="Download a label file template">Template</button>
            </div>
            <input id="importLabelsInput" type="file" accept="application/json" style="display:none">
            <p class="mini" id="memoryStatus"></p>
            <p class="mini" id="importStatus"></p>
          </div>
        </div>
      </aside>

      <main class="main">
        <section class="panel section">
          <div class="selected-toolbar">
            <div>
              <h2>Selected Pair</h2>
              <p class="selected-bar" id="selectedPairBar">No candidate selected.</p>
            </div>
            <div class="button-row selected-actions">
              <button id="prevCandidate">Previous</button>
              <button id="nextCandidate">Next</button>
              <button id="copyCandidateId">Copy ID</button>
            </div>
          </div>
        </section>

        <section class="inspection-grid">
          <div class="panel section">
            <h2>Polygon A</h2>
            <p class="compact-note">Primary geometry and provenance for the first polygon in the selected pair.</p>
            <div id="polyA"></div>
          </div>
          <div class="panel section">
            <h2>Polygon B</h2>
            <p class="compact-note">Primary geometry and provenance for the second polygon in the selected pair.</p>
            <div id="polyB"></div>
          </div>
          <div class="panel section snippet-column">
            <h2>Source DXF Snippets</h2>
            <p class="compact-note">Direct carrier evidence from the raw DXF for the currently selected pair.</p>
            <div id="snippetPanel"></div>
          </div>
        </section>

        <section class="workspace-grid">
          <div class="panel section candidate-pairs-panel">
            <h2>Candidate Pairs</h2>
            <p class="note">These are the pairwise merge candidates under a generous spatial prefilter. The table updates immediately as you move the gates and weights. Click any row to inspect its geometry and consequences.</p>
            <div class="button-row" style="grid-template-columns:repeat(4,minmax(0,1fr));">
              <button data-filter="accepted" class="candidateFilter">Accepted</button>
              <button data-filter="review" class="candidateFilter">Borderline</button>
              <button data-filter="rejected" class="candidateFilter">Rejected</button>
              <button data-filter="all" class="candidateFilter primary">All</button>
            </div>
            <div class="list-shell tall">
              <table>
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Pair</th>
                    <th>Score</th>
                    <th>Gap</th>
                    <th>Angle</th>
                    <th>t-rel</th>
                    <th>Memory</th>
                  </tr>
                </thead>
                <tbody id="candidateBody"></tbody>
              </table>
            </div>
          </div>

          <div class="right-stack">
            <div class="panel section preview-wrap">
              <div>
                <h2>Pair Preview</h2>
                <p class="note">Blue/green/red geometry is the selected family. The selected pair is highlighted; current accepted component context is shown lightly in the background.</p>
              </div>
              <div class="svg-card">
                <div id="pairPreview"></div>
              </div>
            </div>

            <div class="panel section preview-wrap">
              <div>
                <h2>Selected Candidate</h2>
                <p class="note" id="candidateExplain">Select a candidate pair from the table.</p>
              </div>
              <div class="detail-grid">
                <div class="detail-card">
                  <h3>Rule Metrics</h3>
                  <dl id="metricDetails"></dl>
                </div>
                <div class="detail-card">
                  <h3>Decision Consequences</h3>
                  <dl id="decisionDetails"></dl>
                </div>
              </div>
              <div class="button-row">
                <button id="labelPositive" class="good">Mark Positive</button>
                <button id="labelNegative" class="bad">Mark Negative</button>
                <button id="clearLabel">Clear Label</button>
              </div>
              <div id="labelStatus" class="mini"></div>
            </div>
          </div>
        </section>

        <section class="provenance-grid">
          <div class="panel section">
            <h2>Family Layer Provenance</h2>
            <p class="note">These are the raw source layers feeding the current family, grouped by canonicalized layer meaning and kept separate for auditability.</p>
            <div class="list-shell tall">
              <table>
                <thead>
                  <tr>
                    <th>Raw Layer</th>
                    <th>Canonical</th>
                    <th>Kind</th>
                    <th>Count</th>
                    <th>Types</th>
                  </tr>
                </thead>
                <tbody id="familyLayerBody"></tbody>
              </table>
            </div>
          </div>

          <div class="right-stack">
            <div class="panel section">
              <h2>Component Consequences</h2>
              <p class="note">Accepted edges induce connected components. This is the immediate structural consequence of the merge rules you set. Large components are where over-merging shows up first.</p>
              <div class="list-shell">
                <table>
                  <thead>
                    <tr>
                      <th>Component</th>
                      <th>Size</th>
                      <th>Members</th>
                      <th>Bounds</th>
                    </tr>
                  </thead>
                  <tbody id="componentBody"></tbody>
                </table>
              </div>
            </div>

            <div class="panel section">
              <h2>Variant Groups</h2>
              <p class="note">Canonical layer groups show where representation variants coexist. This is provenance that should remain visible even when geometry pools across them.</p>
              <div class="list-shell">
                <table>
                  <thead>
                    <tr>
                      <th>Canonical</th>
                      <th>Kind</th>
                      <th>Raw Layers</th>
                      <th>Note</th>
                    </tr>
                  </thead>
                  <tbody id="variantGroupBody"></tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section class="panel section">
          <div class="summary-grid" id="summaryGrid"></div>
        </section>
      </main>
    </div>
  </div>

  <script id="merge-data" type="application/json">{dataset_json}</script>
  <script>
    const DATA = JSON.parse(document.getElementById('merge-data').textContent);
    const familySelect = document.getElementById('familySelect');
    const summaryGrid = document.getElementById('summaryGrid');
    const selectedPairBar = document.getElementById('selectedPairBar');
    const familyLayerBody = document.getElementById('familyLayerBody');
    const variantGroupBody = document.getElementById('variantGroupBody');
    const candidateBody = document.getElementById('candidateBody');
    const componentBody = document.getElementById('componentBody');
    const pairPreview = document.getElementById('pairPreview');
    const metricDetails = document.getElementById('metricDetails');
    const decisionDetails = document.getElementById('decisionDetails');
    const candidateExplain = document.getElementById('candidateExplain');
    const polyA = document.getElementById('polyA');
    const polyB = document.getElementById('polyB');
    const snippetPanel = document.getElementById('snippetPanel');
    const memoryStatus = document.getElementById('memoryStatus');
    const labelStatus = document.getElementById('labelStatus');
    const familyNote = document.getElementById('familyNote');
    const metaLine = document.getElementById('metaLine');
    const importStatus = document.getElementById('importStatus');
    const importLabelsInput = document.getElementById('importLabelsInput');
    const prevCandidateButton = document.getElementById('prevCandidate');
    const nextCandidateButton = document.getElementById('nextCandidate');
    const copyCandidateIdButton = document.getElementById('copyCandidateId');

    const filterButtons = Array.from(document.querySelectorAll('.candidateFilter'));
    const controlIds = [
      'max_boundary_gap','max_angle_diff','max_thickness_rel','max_area_ratio',
      'max_gap_major_norm','max_gap_minor_norm','min_overlap_major','min_overlap_minor',
      'w_gap','w_angle','w_thickness','w_continuity','w_alignment','w_iou','w_layer',
      'score_threshold','memory_beta','w_memory'
    ];
    const controls = Object.fromEntries(controlIds.map(id => [id, document.getElementById(id)]));

    let currentFamily = 'walls';
    let currentFilter = 'all';
    let selectedCandidateId = null;
    let selectedComponentRoot = null;
    const labelStorageKey = `merge_lab_labels_${{DATA.meta.dataset_id}}`;
    let expertLabels = JSON.parse(localStorage.getItem(labelStorageKey) || '{{}}');
    let importMessage = '';

    function fmt(value, digits = 2) {{
      return Number(value).toLocaleString(undefined, {{minimumFractionDigits: digits, maximumFractionDigits: digits}});
    }}

    function fmtInt(value) {{
      return Number(value).toLocaleString();
    }}

    function shortenText(text, maxLen = 52) {{
      if (!text) return '';
      if (text.length <= maxLen) return text;
      return text.slice(0, maxLen - 1) + '…';
    }}

    function centroid(poly) {{
      return poly.centroid;
    }}

    function setSliderValue(id, value) {{
      controls[id].value = value;
      document.getElementById(`${{id}}_value`).textContent = Number(value).toFixed(id.includes('max_') || id.includes('min_') || id.includes('w_') || id === 'score_threshold' ? 2 : 2);
    }}

    function currentPreset() {{
      const preset = {{}};
      for (const id of controlIds) {{
        preset[id] = Number(controls[id].value);
      }}
      return preset;
    }}

    function normalizeFamilyData() {{
      for (const [family, payload] of Object.entries(DATA.families)) {{
        payload.polygonByIndex = Object.fromEntries(payload.polygons.map(poly => [poly.local_index, poly]));
        payload.candidateById = Object.fromEntries(payload.candidates.map(candidate => [candidate.id, candidate]));
      }}
    }}

    function populateFamilies() {{
      familySelect.innerHTML = '';
      for (const family of Object.keys(DATA.families)) {{
        const option = document.createElement('option');
        option.value = family;
        option.textContent = `${{FAMILY_LABELS[family] || family}} (${{fmtInt(DATA.families[family].stats.candidate_count)}} candidates)`;
        familySelect.appendChild(option);
      }}
    }}

    const FAMILY_LABELS = {json.dumps(FAMILY_LABELS)};
    const FAMILY_COLORS = DATA.meta.family_colors;

    function resetPreset() {{
      const preset = DATA.families[currentFamily].preset;
      for (const id of controlIds) {{
        setSliderValue(id, preset[id]);
      }}
      render();
    }}

    function clamp(min, value, max) {{
      return Math.max(min, Math.min(max, value));
    }}

    function smallerBetter(value, maxValue) {{
      if (maxValue <= 1e-9) return 0;
      return Math.max(-0.5, 1 - value / maxValue);
    }}

    function largerBetter(value, minValue) {{
      if (minValue >= 1) return value;
      return Math.max(-0.5, (value - minValue) / Math.max(1e-9, 1 - minValue));
    }}

    function featureVector(candidate) {{
      return [
        clamp(0, candidate.boundary_gap / Math.max(1, candidate.scale_ref * 6), 3),
        clamp(0, candidate.angle_diff_deg / 90, 2),
        clamp(0, candidate.thickness_rel_diff, 3),
        clamp(0, Math.log(candidate.area_ratio) / Math.log(12), 2),
        clamp(0, candidate.gap_major_norm / 8, 2),
        clamp(0, candidate.gap_minor_norm / 3, 2),
        clamp(0, 1 - candidate.overlap_major_ratio, 2),
        clamp(0, 1 - candidate.overlap_minor_ratio, 2),
        clamp(0, 1 - candidate.bbox_iou, 2),
        clamp(0, 1 - candidate.layer_jaccard, 2)
      ];
    }}

    function normalizeVector(vector) {{
      const norm = Math.sqrt(vector.reduce((acc, value) => acc + value * value, 0));
      if (norm <= 1e-9) return vector.map(() => 0);
      return vector.map(value => value / norm);
    }}

    function cosine(a, b) {{
      let dot = 0;
      for (let i = 0; i < a.length; i += 1) dot += a[i] * b[i];
      return dot;
    }}

    function memoryEnergy(vec, bank, beta) {{
      if (!bank.length) return null;
      const sims = bank.map(item => cosine(vec, item));
      const scaled = sims.map(sim => beta * sim);
      const maxScaled = Math.max(...scaled);
      const denom = scaled.reduce((acc, value) => acc + Math.exp(value - maxScaled), 0);
      return -(maxScaled + Math.log(denom)) / beta;
    }}

    function candidateMemoryMargin(candidate, family, preset) {{
      const familyCandidates = DATA.families[family].candidates;
      const positive = [];
      const negative = [];
      for (const item of familyCandidates) {{
        const label = expertLabels[item.id];
        if (!label) continue;
        const vec = normalizeVector(featureVector(item));
        if (label === 'positive') positive.push(vec);
        if (label === 'negative') negative.push(vec);
      }}
      if (!positive.length && !negative.length) return {{margin: 0, positiveCount: 0, negativeCount: 0}};
      const vec = normalizeVector(featureVector(candidate));
      const ePos = memoryEnergy(vec, positive, preset.memory_beta);
      const eNeg = memoryEnergy(vec, negative, preset.memory_beta);
      const margin = (eNeg === null ? 0 : eNeg) - (ePos === null ? 0 : ePos);
      return {{margin, positiveCount: positive.length, negativeCount: negative.length}};
    }}

    function scoreCandidate(candidate, preset) {{
      let score = 0;
      score += preset.w_gap * smallerBetter(candidate.boundary_gap, preset.max_boundary_gap);
      score += preset.w_angle * smallerBetter(candidate.angle_diff_deg, preset.max_angle_diff);
      score += preset.w_thickness * smallerBetter(candidate.thickness_rel_diff, preset.max_thickness_rel);
      score += preset.w_continuity * (
        0.65 * smallerBetter(candidate.gap_major_norm, preset.max_gap_major_norm) +
        0.35 * largerBetter(candidate.overlap_major_ratio, preset.min_overlap_major)
      );
      score += preset.w_alignment * (
        0.65 * smallerBetter(candidate.gap_minor_norm, preset.max_gap_minor_norm) +
        0.35 * largerBetter(candidate.overlap_minor_ratio, preset.min_overlap_minor)
      );
      score += preset.w_iou * candidate.bbox_iou;
      score += preset.w_layer * candidate.layer_jaccard;
      const memory = candidateMemoryMargin(candidate, currentFamily, preset);
      score += preset.w_memory * memory.margin;
      return {{score, memory}};
    }}

    function hardPass(candidate, preset) {{
      return (
        candidate.boundary_gap <= preset.max_boundary_gap &&
        candidate.angle_diff_deg <= preset.max_angle_diff &&
        candidate.thickness_rel_diff <= preset.max_thickness_rel &&
        candidate.area_ratio <= preset.max_area_ratio &&
        candidate.gap_major_norm <= preset.max_gap_major_norm &&
        candidate.gap_minor_norm <= preset.max_gap_minor_norm &&
        candidate.overlap_major_ratio >= preset.min_overlap_major &&
        candidate.overlap_minor_ratio >= preset.min_overlap_minor
      );
    }}

    function evaluateCandidates() {{
      const preset = currentPreset();
      const payload = DATA.families[currentFamily];
      return payload.candidates.map(candidate => {{
        const scoring = scoreCandidate(candidate, preset);
        const pass = hardPass(candidate, preset);
        const accepted = pass && scoring.score >= preset.score_threshold;
        const delta = scoring.score - preset.score_threshold;
        let status = 'rejected';
        if (accepted) status = 'accepted';
        else if (pass || Math.abs(delta) <= 0.25) status = 'review';
        return {{...candidate, ...scoring, accepted, hard_pass_now: pass, status}};
      }}).sort((a, b) => b.score - a.score);
    }}

    function unionFind(size) {{
      const parent = Array.from({{length: size}}, (_, idx) => idx);
      const rank = Array.from({{length: size}}, () => 0);
      const find = (x) => {{
        while (parent[x] !== x) {{
          parent[x] = parent[parent[x]];
          x = parent[x];
        }}
        return x;
      }};
      const union = (a, b) => {{
        let ra = find(a);
        let rb = find(b);
        if (ra === rb) return;
        if (rank[ra] < rank[rb]) [ra, rb] = [rb, ra];
        parent[rb] = ra;
        if (rank[ra] === rank[rb]) rank[ra] += 1;
      }};
      return {{parent, find, union}};
    }}

    function buildComponents(evaluated) {{
      const payload = DATA.families[currentFamily];
      const uf = unionFind(payload.polygons.length);
      for (const candidate of evaluated) {{
        if (candidate.accepted) uf.union(candidate.a, candidate.b);
      }}
      const groups = new Map();
      for (const poly of payload.polygons) {{
        const root = uf.find(poly.local_index);
        if (!groups.has(root)) groups.set(root, []);
        groups.get(root).push(poly.local_index);
      }}
      const components = Array.from(groups.entries()).map(([root, members]) => {{
        const polys = members.map(idx => payload.polygonByIndex[idx]);
        const bbox = [
          Math.min(...polys.map(p => p.bbox[0])),
          Math.min(...polys.map(p => p.bbox[1])),
          Math.max(...polys.map(p => p.bbox[2])),
          Math.max(...polys.map(p => p.bbox[3])),
        ];
        return {{root, members: members.sort((a, b) => a - b), bbox}};
      }}).sort((a, b) => b.members.length - a.members.length || a.root - b.root);
      return {{uf, components}};
    }}

    function metricCard(label, value, detail, accent) {{
      return `
        <div class="metric" style="--accent:${{accent}}">
          <div class="label">${{label}}</div>
          <div class="value">${{value}}</div>
          <div class="detail">${{detail}}</div>
        </div>
      `;
    }}

    function renderSummary(evaluated, components) {{
      const accepted = evaluated.filter(item => item.accepted);
      const review = evaluated.filter(item => item.status === 'review');
      const payload = DATA.families[currentFamily];
      const biggest = components.components[0] ? components.components[0].members.length : 0;
      const singles = components.components.filter(component => component.members.length === 1).length;
      const familyProv = payload.provenance.family_summary;
      const multiLayer = payload.polygons.filter(poly => poly.source_layers.length > 1).length;
      summaryGrid.innerHTML = [
        metricCard('Family', FAMILY_LABELS[currentFamily], 'Rules and notes in sidebar', FAMILY_COLORS[currentFamily]),
        metricCard('Candidates', fmtInt(payload.stats.candidate_count), `${{fmtInt(accepted.length)}} accepted / ${{fmtInt(review.length)}} borderline`, '#111'),
        metricCard('Components', fmtInt(components.components.length), `${{fmtInt(singles)}} singletons`, '#555'),
        metricCard('Largest Cluster', fmtInt(biggest), 'max merged component size', '#c05f00'),
        metricCard('Raw Layers', fmtInt(familyProv.raw_layer_count), 'scoped source layers for this family', '#7c4dff'),
        metricCard('Variant Groups', fmtInt(familyProv.variant_group_count), `${{fmtInt(familyProv.multi_variant_group_count)}} multi-variant groups`, '#9c6644'),
        metricCard('Multi-Layer Polygons', fmtInt(multiLayer), 'recovered tokens with more than one raw layer', '#007f5f'),
        metricCard('Expert Labels', fmtInt(Object.values(expertLabels).filter(label => label).length), 'local memory bank', '#6c5ce7'),
      ].join('');
    }}

    function renderProvenanceTables() {{
      const payload = DATA.families[currentFamily];
      familyLayerBody.innerHTML = payload.provenance.layer_summaries
        .slice()
        .sort((a, b) => b.entity_count - a.entity_count || a.raw_layer.localeCompare(b.raw_layer))
        .map(item => `
          <tr>
            <td>${{item.raw_layer}}</td>
            <td>${{item.canonical_layer}}</td>
            <td>${{item.group_kind}}</td>
            <td>${{fmtInt(item.entity_count)}}</td>
            <td>${{Object.entries(item.entity_types).map(([k, v]) => `${{k}}:${{v}}`).join(', ')}}</td>
          </tr>
        `).join('');

      variantGroupBody.innerHTML = payload.provenance.variant_groups
        .filter(item => item.raw_layers.length > 1)
        .map(item => `
          <tr>
            <td>${{item.canonical_layer}}</td>
            <td>${{item.group_kind}}</td>
            <td>${{item.raw_layers.join(', ')}}</td>
            <td>${{item.note}}</td>
          </tr>
        `).join('') || `<tr><td colspan="4" class="mini">No multi-variant groups in this family.</td></tr>`;
    }}

    function currentLabelForCandidate(candidateId) {{
      return expertLabels[candidateId] || null;
    }}

    function candidateStatusChip(candidate) {{
      const label = currentLabelForCandidate(candidate.id);
      let extra = '';
      if (label === 'positive') extra = ' labeled-pos';
      if (label === 'negative') extra = ' labeled-neg';
      return `<span class="chip ${{candidate.status}}${{extra}}">${{candidate.status}}</span>`;
    }}

    function renderCandidateTable(evaluated) {{
      let rows = evaluated;
      if (currentFilter !== 'all') rows = rows.filter(item => item.status === currentFilter);
      rows = rows.slice(0, 160);
      candidateBody.innerHTML = rows.map(candidate => {{
        const payload = DATA.families[currentFamily];
        const polyA = payload.polygonByIndex[candidate.a];
        const polyB = payload.polygonByIndex[candidate.b];
        const activeClass = candidate.id === selectedCandidateId ? 'active' : '';
        return `
          <tr class="${{activeClass}}" data-candidate-id="${{candidate.id}}">
            <td>${{candidateStatusChip(candidate)}}</td>
            <td><strong>${{polyA.id}}</strong> + <strong>${{polyB.id}}</strong><br><span class="mini">${{candidate.id}}</span></td>
            <td>${{fmt(candidate.score, 2)}}</td>
            <td>${{fmt(candidate.boundary_gap, 1)}}</td>
            <td>${{fmt(candidate.angle_diff_deg, 1)}}°</td>
            <td>${{fmt(candidate.thickness_rel_diff, 2)}}</td>
            <td>${{fmt(candidate.memory.margin, 2)}}</td>
          </tr>
        `;
      }}).join('');

      candidateBody.querySelectorAll('tr[data-candidate-id]').forEach(row => {{
        row.addEventListener('click', () => {{
          selectedCandidateId = row.dataset.candidateId;
          selectedComponentRoot = null;
          render();
        }});
      }});
    }}

    function chooseDefaultCandidate(evaluated) {{
      let rows = evaluated;
      if (currentFilter !== 'all') rows = rows.filter(item => item.status === currentFilter);
      if (!rows.length) rows = evaluated;
      return rows.length ? rows[0].id : null;
    }}

    function ensureSelection(evaluated) {{
      const current = selectedCandidateId ? evaluated.find(item => item.id === selectedCandidateId) : null;
      if (current) {{
        if (currentFilter === 'all' || current.status === currentFilter) return;
      }}
      if (selectedComponentRoot !== null) return;
      selectedCandidateId = chooseDefaultCandidate(evaluated);
    }}

    function visibleCandidates(evaluated) {{
      let rows = evaluated;
      if (currentFilter !== 'all') rows = rows.filter(item => item.status === currentFilter);
      if (!rows.length) rows = evaluated;
      return rows;
    }}

    function currentSelectionIndex(evaluated) {{
      const rows = visibleCandidates(evaluated);
      const index = rows.findIndex(item => item.id === selectedCandidateId);
      return {{rows, index}};
    }}

    function renderSelectedPairBar(evaluated) {{
      const payload = DATA.families[currentFamily];
      const {{rows, index}} = currentSelectionIndex(evaluated);
      const candidate = selectedCandidateId ? evaluated.find(item => item.id === selectedCandidateId) : null;

      if (!candidate) {{
        selectedPairBar.textContent = 'No candidate selected.';
        prevCandidateButton.disabled = true;
        nextCandidateButton.disabled = true;
        copyCandidateIdButton.disabled = true;
        return;
      }}

      const a = payload.polygonByIndex[candidate.a];
      const b = payload.polygonByIndex[candidate.b];
      const rank = index >= 0 ? `${{index + 1}} of ${{rows.length}}` : `1 of ${{rows.length}}`;
      const la = a.source_layers.join(', ');
      const lb = b.source_layers.join(', ');
      const layersPart = la === lb
        ? `layers ${{shortenText(la, 72)}}`
        : `layers ${{shortenText(la, 36)}} | ${{shortenText(lb, 36)}}`;
      selectedPairBar.textContent = `Candidate ${{candidate.id}} · rank ${{rank}} · ${{a.id}} + ${{b.id}} · ${{candidate.status}} · ${{layersPart}}`;
      prevCandidateButton.disabled = !(rows.length && index > 0);
      nextCandidateButton.disabled = !(rows.length && index >= 0 && index < rows.length - 1);
      copyCandidateIdButton.disabled = false;
    }}

    function moveSelection(direction) {{
      const {{rows, index}} = currentSelectionIndex(evaluatedState);
      if (!rows.length) return;
      const fallback = index >= 0 ? index : 0;
      const nextIndex = Math.max(0, Math.min(rows.length - 1, fallback + direction));
      selectedCandidateId = rows[nextIndex].id;
      selectedComponentRoot = null;
      render();
    }}

    async function copySelectedCandidateId() {{
      if (!selectedCandidateId) return;
      try {{
        await navigator.clipboard.writeText(selectedCandidateId);
        importMessage = `Copied candidate id ${{selectedCandidateId}} to clipboard.`;
      }} catch (error) {{
        importMessage = `Copy failed. Candidate id: ${{selectedCandidateId}}`;
      }}
      render();
    }}

    function renderComponentTable(evaluated, components) {{
      const payload = DATA.families[currentFamily];
      componentBody.innerHTML = components.components.slice(0, 120).map(component => {{
        const labels = component.members.slice(0, 6).map(index => payload.polygonByIndex[index].id).join(', ');
        const more = component.members.length > 6 ? ` +${{component.members.length - 6}} more` : '';
        const activeClass = component.root === selectedComponentRoot ? 'active' : '';
        return `
          <tr class="${{activeClass}}" data-root="${{component.root}}">
            <td><span class="chip">${{currentFamily.slice(0,2)}}-${{component.root}}</span></td>
            <td>${{fmtInt(component.members.length)}}</td>
            <td>${{labels}}${{more}}</td>
            <td>${{component.bbox.map(v => fmt(v, 0)).join(', ')}}</td>
          </tr>
        `;
      }}).join('');

      componentBody.querySelectorAll('tr[data-root]').forEach(row => {{
        row.addEventListener('click', () => {{
          selectedComponentRoot = Number(row.dataset.root);
          render();
        }});
      }});
    }}

    function componentMembersForCurrentSelection(components) {{
      if (selectedComponentRoot !== null) {{
        const component = components.components.find(item => item.root === selectedComponentRoot);
        return component ? component.members : [];
      }}
      if (!selectedCandidateId) return [];
      const candidate = evaluatedState.find(item => item.id === selectedCandidateId);
      if (!candidate) return [];
      const root = components.uf.find(candidate.a);
      const component = components.components.find(item => item.root === root);
      return component ? component.members : [];
    }}

    function bboxOfPolygons(polygons) {{
      return [
        Math.min(...polygons.map(poly => poly.bbox[0])),
        Math.min(...polygons.map(poly => poly.bbox[1])),
        Math.max(...polygons.map(poly => poly.bbox[2])),
        Math.max(...polygons.map(poly => poly.bbox[3])),
      ];
    }}

    function expandBBox(bbox, padRatio = 0.45, minPad = 60) {{
      const width = bbox[2] - bbox[0];
      const height = bbox[3] - bbox[1];
      const pad = Math.max(minPad, Math.max(width, height) * padRatio);
      return [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad];
    }}

    function renderSvg(polygons, highlightedIds, bbox) {{
      if (!polygons.length) return '<div class="note">No geometry.</div>';
      const width = 760;
      const pad = 24;
      const spanX = Math.max(1, bbox[2] - bbox[0]);
      const spanY = Math.max(1, bbox[3] - bbox[1]);
      const scale = (width - pad * 2) / spanX;
      const height = Math.ceil(spanY * scale + pad * 2);
      const project = (point) => {{
        const x = pad + (point[0] - bbox[0]) * scale;
        const y = pad + (bbox[3] - point[1]) * scale;
        return [x, y];
      }};
      const pieces = [
        `<svg class="viewer" viewBox="0 0 ${{width}} ${{height}}" xmlns="http://www.w3.org/2000/svg">`,
        `<rect x="0" y="0" width="${{width}}" height="${{height}}" fill="#ffffff"/>`
      ];
      const color = FAMILY_COLORS[currentFamily];
      for (const poly of polygons) {{
        const pts = poly.vertices.map(project).map(([x, y]) => `${{x.toFixed(2)}},${{y.toFixed(2)}}`).join(' ');
        const active = highlightedIds.has(poly.local_index);
        const fillOpacity = active ? 0.22 : 0.05;
        const strokeOpacity = active ? 1.0 : 0.28;
        const strokeWidth = active ? 2.8 : 1.2;
        pieces.push(`<polygon points="${{pts}}" fill="${{color}}" fill-opacity="${{fillOpacity}}" stroke="${{color}}" stroke-opacity="${{strokeOpacity}}" stroke-width="${{strokeWidth}}"/>`);
        if (active) {{
          const cx = poly.centroid[0];
          const cy = poly.centroid[1];
          const [tx, ty] = project([cx, cy]);
          pieces.push(`<circle cx="${{tx.toFixed(2)}}" cy="${{ty.toFixed(2)}}" r="3.2" fill="${{color}}" />`);
          pieces.push(`<text x="${{(tx + 6).toFixed(2)}}" y="${{(ty - 6).toFixed(2)}}" font-size="12" font-weight="700" fill="#111">${{poly.id}}</text>`);
        }}
      }}
      pieces.push('</svg>');
      return pieces.join('');
    }}

    function renderSelection(evaluated, components) {{
      const payload = DATA.families[currentFamily];
      const candidate = selectedCandidateId ? evaluated.find(item => item.id === selectedCandidateId) : null;
      const memberIds = componentMembersForCurrentSelection(components);
      const componentPolys = memberIds.map(id => payload.polygonByIndex[id]);

      if (candidate) {{
        const a = payload.polygonByIndex[candidate.a];
        const b = payload.polygonByIndex[candidate.b];
        const bbox = expandBBox(bboxOfPolygons(componentPolys.length ? componentPolys : [a, b]), 0.35, 45);
        pairPreview.innerHTML = renderSvg(componentPolys.length ? componentPolys : [a, b], new Set([candidate.a, candidate.b]), bbox);
        candidateExplain.textContent = `Candidate ${{candidate.id}} | ${{a.id}} + ${{b.id}} | status: ${{candidate.status}} | heuristic ${{fmt(candidate.score, 2)}} | memory margin ${{fmt(candidate.memory.margin, 2)}} | layers: [${{a.source_layers.join(', ')}}] + [${{b.source_layers.join(', ')}}]`;

        const preset = currentPreset();
        const rootA = components.uf.find(candidate.a);
        const rootB = components.uf.find(candidate.b);
        const compA = components.components.find(component => component.root === rootA);
        const compB = components.components.find(component => component.root === rootB);
        const potentialSize = rootA === rootB ? compA.members.length : compA.members.length + compB.members.length;
        const label = currentLabelForCandidate(candidate.id);
        labelStatus.textContent = label ? `Expert label: ${{label}}` : 'No expert label stored for this candidate.';

        metricDetails.innerHTML = [
          ['boundary gap', fmt(candidate.boundary_gap, 2)],
          ['angle diff', `${{fmt(candidate.angle_diff_deg, 2)}}°`],
          ['thickness rel diff', fmt(candidate.thickness_rel_diff, 3)],
          ['area ratio', fmt(candidate.area_ratio, 3)],
          ['gap major / scale', fmt(candidate.gap_major_norm, 3)],
          ['gap minor / scale', fmt(candidate.gap_minor_norm, 3)],
          ['overlap major', fmt(candidate.overlap_major_ratio, 3)],
          ['overlap minor', fmt(candidate.overlap_minor_ratio, 3)],
          ['bbox IoU', fmt(candidate.bbox_iou, 3)],
          ['layer Jaccard', fmt(candidate.layer_jaccard, 3)],
        ].map(([k, v]) => `<dt>${{k}}</dt><dd>${{v}}</dd>`).join('');

        decisionDetails.innerHTML = [
          ['hard pass', candidate.hard_pass_now ? 'yes' : 'no'],
          ['score threshold', fmt(preset.score_threshold, 2)],
          ['accepted now', candidate.accepted ? 'yes' : 'no'],
          ['component size if linked', fmtInt(potentialSize)],
          ['memory positives', fmtInt(candidate.memory.positiveCount)],
          ['memory negatives', fmtInt(candidate.memory.negativeCount)],
          ['memory margin', fmt(candidate.memory.margin, 3)],
        ].map(([k, v]) => `<dt>${{k}}</dt><dd>${{v}}</dd>`).join('');

        polyA.innerHTML = polygonCard(a, candidate.a === candidate.b ? [a] : componentPolys);
        polyB.innerHTML = polygonCard(b, candidate.a === candidate.b ? [b] : componentPolys);
        snippetPanel.innerHTML = snippetsHtml(a, b);
      }} else {{
        pairPreview.innerHTML = '<div class="note" style="padding:18px;">Select a candidate or a component.</div>';
        candidateExplain.textContent = 'Select a candidate pair from the table.';
        metricDetails.innerHTML = '';
        decisionDetails.innerHTML = '';
        polyA.innerHTML = '<div class="note">No polygon selected.</div>';
        polyB.innerHTML = '<div class="note">No polygon selected.</div>';
        snippetPanel.innerHTML = '<div class="note">No DXF snippet selected.</div>';
        labelStatus.textContent = '';
      }}

      if (!candidate && selectedComponentRoot !== null) {{
        const component = components.components.find(item => item.root === selectedComponentRoot);
        if (component) {{
          const polys = component.members.map(id => payload.polygonByIndex[id]);
          const bbox = expandBBox(component.bbox, 0.25, 50);
          pairPreview.innerHTML = renderSvg(polys, new Set(component.members), bbox);
          candidateExplain.textContent = `Component ${{selectedComponentRoot}} with ${{component.members.length}} members.`;
          polyA.innerHTML = `<div class="note">${{component.members.map(id => payload.polygonByIndex[id].id).join(', ')}}</div>`;
          polyB.innerHTML = `<div class="note">Inspect a candidate inside this component for pair-level detail.</div>`;
        }}
      }}
    }}

    function polygonCard(poly) {{
      const layerRows = poly.source_layer_details.map(item => `
        <tr>
          <td>${{item.raw_layer}}</td>
          <td>${{item.canonical_layer}}</td>
          <td>${{item.group_kind}}</td>
          <td>${{fmtInt(item.entity_count)}}</td>
        </tr>
      `).join('');
      const variantBlocks = poly.source_variant_groups.map(group => `
        <details>
          <summary>${{group.canonical_layer}} (${{group.group_kind}})</summary>
          <div class="mini">${{group.note}}</div>
          <div class="mini">raw layers: ${{group.raw_layers.join(', ')}}</div>
        </details>
      `).join('');
      return `
        <div class="chip" style="margin-bottom:8px;">${{poly.id}}</div>
        <dl>
          <dt>area</dt><dd>${{fmt(poly.area, 1)}}</dd>
          <dt>perimeter</dt><dd>${{fmt(poly.perimeter, 1)}}</dd>
          <dt>aspect</dt><dd>${{fmt(poly.aspect_ratio, 2)}}</dd>
          <dt>orientation</dt><dd>${{fmt(poly.orientation_deg, 1)}}°</dd>
          <dt>span</dt><dd>${{fmt(poly.span, 1)}}</dd>
          <dt>thickness</dt><dd>${{fmt(poly.thickness, 1)}}</dd>
          <dt>layers</dt><dd>${{poly.source_layers.join(', ')}}</dd>
          <dt>source entities</dt><dd>${{fmtInt(poly.source_entity_count)}}</dd>
          <dt>source types</dt><dd>${{Object.entries(poly.source_entity_types).map(([k, v]) => `${{k}}:${{v}}`).join(', ')}}</dd>
          <dt>source kind</dt><dd>${{poly.source_kind}}</dd>
        </dl>
        <details>
          <summary>Layer provenance</summary>
          <table>
            <thead><tr><th>Raw</th><th>Canonical</th><th>Kind</th><th>Count</th></tr></thead>
            <tbody>${{layerRows}}</tbody>
          </table>
        </details>
        ${{variantBlocks}}
      `;
    }}

    function snippetsHtml(a, b) {{
      const format = (poly) => {{
        const blocks = poly.snippets.length ? poly.snippets.map(snippet => `
          <details>
            <summary>${{snippet.entity_type}} on ${{snippet.layer}}</summary>
            <pre>${{escapeHtml(snippet.text)}}</pre>
          </details>
        `).join('') : '<div class="note">No snippet.</div>';
        return `<div class="detail-card"><h3>${{poly.id}}</h3>${{blocks}}</div>`;
      }};
      return format(a) + format(b);
    }}

    function escapeHtml(text) {{
      return text
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
    }}

    function setLabel(kind) {{
      if (!selectedCandidateId) return;
      if (!kind) delete expertLabels[selectedCandidateId];
      else expertLabels[selectedCandidateId] = kind;
      localStorage.setItem(labelStorageKey, JSON.stringify(expertLabels));
      render();
    }}

    function buildLabelPackage() {{
      const counts = {{
        positive: Object.values(expertLabels).filter(value => value === 'positive').length,
        negative: Object.values(expertLabels).filter(value => value === 'negative').length,
      }};
      return {{
        schema_version: 1,
        dataset_id: DATA.meta.dataset_id,
        input_file: DATA.meta.input_file,
        snap_tolerance: DATA.meta.snap_tolerance,
        exported_at: new Date().toISOString(),
        counts,
        labels: expertLabels,
      }};
    }}

    function exportLabels() {{
      const payload = buildLabelPackage();
      const blob = new Blob([JSON.stringify(payload, null, 2)], {{type: 'application/json'}});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const safeDataset = DATA.meta.dataset_id.replaceAll(/[^a-zA-Z0-9._-]+/g, '_');
      link.download = `merge_lab_labels_${{safeDataset}}.json`;
      link.click();
      URL.revokeObjectURL(url);
    }}

    function exportAccepted() {{
      const accepted = evaluateCandidates().filter(candidate => candidate.accepted).map(candidate => {{
        const payload = DATA.families[currentFamily];
        return {{
          candidate_id: candidate.id,
          family: currentFamily,
          polygon_a: payload.polygonByIndex[candidate.a].id,
          polygon_b: payload.polygonByIndex[candidate.b].id,
          score: candidate.score,
          hard_pass: candidate.hard_pass_now,
          memory_margin: candidate.memory.margin,
          metrics: {{
            boundary_gap: candidate.boundary_gap,
            angle_diff_deg: candidate.angle_diff_deg,
            thickness_rel_diff: candidate.thickness_rel_diff,
            area_ratio: candidate.area_ratio,
            gap_major_norm: candidate.gap_major_norm,
            gap_minor_norm: candidate.gap_minor_norm,
            overlap_major_ratio: candidate.overlap_major_ratio,
            overlap_minor_ratio: candidate.overlap_minor_ratio,
            bbox_iou: candidate.bbox_iou,
            layer_jaccard: candidate.layer_jaccard,
          }},
        }};
      }});
      const blob = new Blob([JSON.stringify({{
        schema_version: 1,
        dataset_id: DATA.meta.dataset_id,
        family: currentFamily,
        exported_at: new Date().toISOString(),
        accepted,
      }}, null, 2)], {{type: 'application/json'}});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `merge_lab_accepted_${{currentFamily}}.json`;
      link.click();
      URL.revokeObjectURL(url);
    }}

    function normalizeImportedPayload(payload) {{
      if (!payload || typeof payload !== 'object') throw new Error('Label file must be JSON.');
      if (payload.labels && typeof payload.labels === 'object') return payload.labels;
      return payload;
    }}

    function importLabelsFromFile(file) {{
      const reader = new FileReader();
      reader.onload = () => {{
        try {{
          const payload = JSON.parse(reader.result);
          const labels = normalizeImportedPayload(payload);
          let imported = 0;
          for (const [candidateId, label] of Object.entries(labels)) {{
            if (!['positive', 'negative'].includes(label)) continue;
            const family = candidateId.split(':')[0];
            if (!DATA.families[family] || !DATA.families[family].candidateById[candidateId]) continue;
            expertLabels[candidateId] = label;
            imported += 1;
          }}
          localStorage.setItem(labelStorageKey, JSON.stringify(expertLabels));
          importMessage = `Imported ${{imported}} label(s) from ${{file.name}}.`;
          render();
        }} catch (error) {{
          importMessage = `Import failed: ${{error.message}}`;
          render();
        }}
      }};
      reader.onerror = () => {{
        importMessage = `Import failed: could not read ${{file.name}}.`;
        render();
      }};
      reader.readAsText(file);
    }}

    function downloadTemplate() {{
      const template = {{
        schema_version: 1,
        dataset_id: DATA.meta.dataset_id,
        input_file: DATA.meta.input_file,
        snap_tolerance: DATA.meta.snap_tolerance,
        labels: {{
          "walls:0:1": "positive",
          "columns:2:9": "negative"
        }}
      }};
      const blob = new Blob([JSON.stringify(template, null, 2)], {{type: 'application/json'}});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'merge_lab_label_template.json';
      link.click();
      URL.revokeObjectURL(url);
    }}

    function clearLabels() {{
      expertLabels = {{}};
      localStorage.removeItem(labelStorageKey);
      importMessage = 'Cleared all locally stored expert labels.';
      render();
    }}

    let evaluatedState = [];

    function render() {{
      familyNote.textContent = DATA.families[currentFamily].note;
      metaLine.textContent = `${{DATA.meta.input_file}} | snap tolerance ${{DATA.meta.snap_tolerance}} | generated in ${{fmt(DATA.meta.generated_runtime_seconds, 2)}}s`;
      evaluatedState = evaluateCandidates();
      ensureSelection(evaluatedState);
      const components = buildComponents(evaluatedState);
      renderSummary(evaluatedState, components);
      renderSelectedPairBar(evaluatedState);
      renderProvenanceTables();
      renderCandidateTable(evaluatedState);
      renderComponentTable(evaluatedState, components);
      renderSelection(evaluatedState, components);
      const positiveCount = Object.values(expertLabels).filter(value => value === 'positive').length;
      const negativeCount = Object.values(expertLabels).filter(value => value === 'negative').length;
      memoryStatus.textContent = `${{positiveCount}} positive exemplar(s), ${{negativeCount}} negative exemplar(s) in local storage.`;
      importStatus.textContent = importMessage;
      filterButtons.forEach(button => {{
        button.classList.toggle('primary', button.dataset.filter === currentFilter);
      }});
    }}

    familySelect.addEventListener('change', () => {{
      currentFamily = familySelect.value;
      selectedCandidateId = null;
      selectedComponentRoot = null;
      resetPreset();
    }});

    for (const id of controlIds) {{
      controls[id].addEventListener('input', () => {{
        setSliderValue(id, controls[id].value);
        render();
      }});
    }}

    filterButtons.forEach(button => {{
      button.addEventListener('click', () => {{
        currentFilter = button.dataset.filter;
        render();
      }});
    }});

    document.getElementById('resetPreset').addEventListener('click', resetPreset);
    document.getElementById('labelPositive').addEventListener('click', () => setLabel('positive'));
    document.getElementById('labelNegative').addEventListener('click', () => setLabel('negative'));
    document.getElementById('clearLabel').addEventListener('click', () => setLabel(null));
    document.getElementById('exportLabels').addEventListener('click', exportLabels);
    document.getElementById('exportAccepted').addEventListener('click', exportAccepted);
    document.getElementById('importLabels').addEventListener('click', () => importLabelsInput.click());
    document.getElementById('clearLabels').addEventListener('click', clearLabels);
    document.getElementById('downloadTemplate').addEventListener('click', downloadTemplate);
    prevCandidateButton.addEventListener('click', () => moveSelection(-1));
    nextCandidateButton.addEventListener('click', () => moveSelection(1));
    copyCandidateIdButton.addEventListener('click', copySelectedCandidateId);
    importLabelsInput.addEventListener('change', (event) => {{
      const [file] = event.target.files || [];
      if (!file) return;
      importLabelsFromFile(file);
      event.target.value = '';
    }});

    normalizeFamilyData();
    populateFamilies();
    familySelect.value = currentFamily;
    resetPreset();
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an expert-in-the-loop merge lab for polygon normalization and merging.")
    parser.add_argument("input_dxf", type=Path, help="Source DXF file.")
    parser.add_argument("output_dir", type=Path, help="Output directory for merge_lab.html.")
    parser.add_argument("--snap-tolerance", type=float, default=0.5, help="Snap tolerance for polygon extraction.")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    dataset = build_dataset(args.input_dxf, args.snap_tolerance)
    (args.output_dir / "merge_lab_data.json").write_text(json.dumps(dataset, indent=2), encoding="utf-8")
    (args.output_dir / "merge_lab.html").write_text(build_html(dataset), encoding="utf-8")


if __name__ == "__main__":
    main()
