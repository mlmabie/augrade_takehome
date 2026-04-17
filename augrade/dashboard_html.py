#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import tokenize_dxf as td

from . import provenance as pu
from .geometry import entity_to_dxf_snippet as _entity_to_dxf_snippet
from .merge import FAMILY_LABELS


def fmt_int(value: int) -> str:
    return f"{value:,}"


def fmt_float(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def bbox_intersects(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def expand_bbox(bbox: Tuple[float, float, float, float], pad_ratio: float = 0.8, min_pad: float = 80.0) -> Tuple[float, float, float, float]:
    min_x, min_y, max_x, max_y = bbox
    width = max_x - min_x
    height = max_y - min_y
    pad = max(min_pad, max(width, height) * pad_ratio)
    return min_x - pad, min_y - pad, max_x + pad, max_y + pad


def quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[low]
    weight = pos - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def summarize_numeric(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {"count": 0, "min": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "count": len(values),
        "min": min(values),
        "p25": quantile(values, 0.25),
        "p50": quantile(values, 0.50),
        "p75": quantile(values, 0.75),
        "max": max(values),
        "mean": statistics.fmean(values),
    }


def histogram(values: Sequence[float], bins: int = 12) -> List[Tuple[str, int]]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if math.isclose(low, high):
        return [(f"{low:.1f}", len(values))]
    step = (high - low) / bins
    counts = [0 for _ in range(bins)]
    for value in values:
        idx = min(bins - 1, int((value - low) / step))
        counts[idx] += 1
    output = []
    for idx, count in enumerate(counts):
        left = low + idx * step
        right = left + step
        output.append((f"{left:.1f}-{right:.1f}", count))
    return output


def shorten_label(text: str, max_chars: int = 40) -> str:
    """Middle-ellipsis for long chart labels so leading characters stay visible."""
    if len(text) <= max_chars:
        return text
    if max_chars <= 5:
        return text[:max_chars]
    keep = (max_chars - 1) // 2
    tail = max_chars - 1 - keep
    return f"{text[:keep]}…{text[-tail:]}"


def table_html(headers: Sequence[str], rows: Sequence[Sequence[str]], table_class: str = "") -> str:
    class_attr = f' class="{table_class}"' if table_class else ""
    thead = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        body_rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    return f"<table{class_attr}><thead><tr>{thead}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def bar_chart_svg(data: Sequence[Tuple[str, float]], color: str, width: int = 520, height: int = 260) -> str:
    if not data:
        return "<div class='empty'>No data</div>"
    margin_top = 16
    margin_bottom = 16
    margin_right = 58
    bar_gap = 8
    labels = [shorten_label(str(label), 44) for label, _ in data]
    longest_raw = max((len(str(label)) for label, _ in data), default=0)
    longest_disp = max((len(s) for s in labels), default=0)
    longest = max(longest_raw, longest_disp)
    margin_left = int(min(400, max(160, longest * 7.0 + 34)))
    chart_width = max(40, width - margin_left - margin_right - 10)
    chart_height = height - margin_top - margin_bottom
    max_value = max(value for _, value in data) or 1.0
    bar_height = max(12, (chart_height - bar_gap * (len(data) - 1)) / max(len(data), 1))
    value_x = width - 6
    y = margin_top
    parts = [
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg" xmlns="http://www.w3.org/2000/svg">',
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="12" fill="#fbfbfd"/>',
    ]
    for (label, value), display_label in zip(data, labels):
        w = 0 if max_value == 0 else chart_width * value / max_value
        safe_label = html.escape(display_label)
        parts.append(f'<text x="{margin_left - 8}" y="{y + bar_height * 0.72:.1f}" text-anchor="end" font-size="12" fill="#333">{safe_label}</text>')
        parts.append(f'<rect x="{margin_left}" y="{y:.1f}" width="{w:.1f}" height="{bar_height:.1f}" rx="6" fill="{color}" fill-opacity="0.85"/>')
        if isinstance(value, float):
            value_text = fmt_float(value, 1)
        elif isinstance(value, int):
            value_text = fmt_int(value)
        else:
            value_text = str(value)
        parts.append(
            f'<text x="{value_x}" y="{y + bar_height * 0.72:.1f}" text-anchor="end" font-size="12" fill="#333">{html.escape(value_text)}</text>'
        )
        y += bar_height + bar_gap
    parts.append("</svg>")
    return "".join(parts)


def histogram_svg(data: Sequence[Tuple[str, int]], color: str, width: int = 520, height: int = 230) -> str:
    if not data:
        return "<div class='empty'>No data</div>"
    margin_left = 36
    margin_bottom = 58
    margin_top = 18
    chart_width = width - margin_left - 18
    chart_height = height - margin_top - margin_bottom
    max_count = max(count for _, count in data) or 1
    bar_width = chart_width / max(len(data), 1)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg" xmlns="http://www.w3.org/2000/svg">',
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="12" fill="#fbfbfd"/>',
    ]
    for idx, (label, count) in enumerate(data):
        x = margin_left + idx * bar_width + 2
        h = chart_height * count / max_count
        y = margin_top + chart_height - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(bar_width - 4, 2):.1f}" height="{h:.1f}" rx="4" fill="{color}" fill-opacity="0.82"/>')
        parts.append(f'<text x="{x + (bar_width - 4) / 2:.1f}" y="{height - 24}" text-anchor="end" transform="rotate(-45 {x + (bar_width - 4) / 2:.1f},{height - 24})" font-size="9" fill="#444">{html.escape(label)}</text>')
        parts.append(f'<text x="{x + (bar_width - 4) / 2:.1f}" y="{y - 4:.1f}" text-anchor="middle" font-size="10" fill="#444">{count}</text>')
    parts.append("</svg>")
    return "".join(parts)


def metric_card(title: str, value: str, detail: str, accent: str) -> str:
    return (
        f"<div class='metric-card' style='--accent:{accent}'>"
        f"<div class='metric-title'>{html.escape(title)}</div>"
        f"<div class='metric-value'>{html.escape(value)}</div>"
        f"<div class='metric-detail'>{html.escape(detail)}</div>"
        f"</div>"
    )


def entity_to_dxf_snippet(entity: td.Entity, max_lines: int = 44) -> str:
    return _entity_to_dxf_snippet(entity, max_lines=max_lines)


def select_unique_indices(length: int, candidates: Sequence[int]) -> List[int]:
    selected: List[int] = []
    for candidate in candidates:
        idx = max(0, min(length - 1, candidate))
        if idx in selected:
            for delta in range(1, length):
                for alt in (idx - delta, idx + delta):
                    if 0 <= alt < length and alt not in selected:
                        idx = alt
                        break
                else:
                    continue
                break
        if idx not in selected:
            selected.append(idx)
    return selected


def representative_specs(family: str, polygons: Sequence[td.PolygonRecord]) -> List[Tuple[str, td.PolygonRecord]]:
    if not polygons:
        return []
    by_area = sorted(polygons, key=lambda polygon: polygon.area)
    by_aspect = sorted(polygons, key=lambda polygon: polygon.aspect_ratio)
    if family == "walls":
        idxs = select_unique_indices(len(by_area), [len(by_area) // 3, len(by_area) // 2, len(by_area) - 1])
        reps = [
            ("Wall, lower-mid area", by_area[idxs[0]]),
            ("Wall, median area", by_area[idxs[1]]),
            ("Wall, highest aspect", by_aspect[-1]),
        ]
    elif family == "columns":
        idxs = select_unique_indices(len(by_area), [max(0, len(by_area) // 6), len(by_area) // 2, len(by_area) - 1])
        reps = [
            ("Column, small", by_area[idxs[0]]),
            ("Column, typical", by_area[idxs[1]]),
            ("Column, large", by_area[idxs[2]]),
        ]
    else:
        idxs = select_unique_indices(len(by_area), [max(0, len(by_area) // 5), len(by_area) // 2, len(by_area) - 1])
        reps = [
            ("Curtain wall, small", by_area[idxs[0]]),
            ("Curtain wall, typical", by_area[idxs[1]]),
            ("Curtain wall, highest aspect", by_aspect[-1]),
        ]

    seen = set()
    unique_reps = []
    for label, polygon in reps:
        sig = (polygon.family, round(polygon.area, 3), round(polygon.bbox[0], 3), round(polygon.bbox[1], 3), round(polygon.bbox[2], 3), round(polygon.bbox[3], 3))
        if sig in seen:
            continue
        seen.add(sig)
        unique_reps.append((label, polygon))
    return unique_reps


def write_zoom_svg(
    path: Path,
    extent: Tuple[float, float, float, float],
    entities: Sequence[td.Entity],
    polygons: Sequence[td.PolygonRecord],
    selected: td.PolygonRecord,
) -> None:
    project, width, height = td.svg_transform(extent, width=620, padding=28)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>',
    ]

    for entity in entities:
        color = "#b5b5ba"
        opacity = "0.45"
        if entity.family in td.FAMILY_COLORS:
            color = td.FAMILY_COLORS[entity.family]
            opacity = "0.22"
        for draw_path in td.entity_to_draw_paths(entity):
            if len(draw_path) < 2:
                continue
            projected = [project(point) for point in draw_path]
            point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in projected)
            lines.append(f'<polyline fill="none" stroke="{color}" stroke-opacity="{opacity}" stroke-width="1" points="{point_text}"/>')

    for polygon in polygons:
        projected = [project(point) for point in polygon.vertices]
        point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in projected)
        color = td.FAMILY_COLORS[polygon.family]
        lines.append(f'<polygon fill="{color}" fill-opacity="0.08" stroke="{color}" stroke-opacity="0.25" stroke-width="1" points="{point_text}"/>')

    projected = [project(point) for point in selected.vertices]
    point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in projected)
    highlight = td.FAMILY_COLORS[selected.family]
    lines.append(f'<polygon fill="{highlight}" fill-opacity="0.20" stroke="{highlight}" stroke-width="2.2" points="{point_text}"/>')
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def collect_representative_assets(
    entities: Sequence[td.Entity],
    polygons: Sequence[td.PolygonRecord],
    provenance: Dict[str, object],
    output_dir: Path,
) -> List[Dict[str, object]]:
    assets_dir = output_dir / "dashboard_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    target_entities = [entity for entity in entities if entity.family]
    entity_extents = {entity.entity_id: td.entity_extent(entity) for entity in target_entities}
    entity_by_id = {entity.entity_id: entity for entity in target_entities}
    layer_summaries = provenance["layer_summaries"]
    variant_groups_by_id = provenance["variant_groups_by_id"]
    polygons_by_family: Dict[str, List[td.PolygonRecord]] = defaultdict(list)
    for polygon in polygons:
        polygons_by_family[polygon.family].append(polygon)

    gallery: List[Dict[str, object]] = []
    for family in ["walls", "columns", "curtain_walls"]:
        for idx, (label, polygon) in enumerate(representative_specs(family, polygons_by_family[family]), start=1):
            extent = expand_bbox(polygon.bbox)
            nearby_entities = [
                entity for entity in target_entities
                if entity_extents[entity.entity_id] is not None and bbox_intersects(extent, entity_extents[entity.entity_id])
            ]
            nearby_polygons = [candidate for candidate in polygons if bbox_intersects(extent, candidate.bbox)]
            slug = f"{family}_{idx:02d}"
            svg_path = assets_dir / f"{slug}.svg"
            write_zoom_svg(svg_path, extent, nearby_entities, nearby_polygons, polygon)

            snippet_entities = []
            priority = {"CIRCLE": 0, "ARC": 1, "LINE": 2, "LWPOLYLINE": 3, "POLYLINE": 4, "ELLIPSE": 5}
            for entity_id in sorted(polygon.source_entity_ids, key=lambda item: priority.get(entity_by_id[item].type, 99) if item in entity_by_id else 99):
                if entity_id in entity_by_id:
                    snippet_entities.append(entity_by_id[entity_id])
                if len(snippet_entities) >= 2:
                    break

            source_type_counter = Counter()
            for entity_id in polygon.source_entity_ids:
                entity = entity_by_id.get(entity_id)
                if entity is not None:
                    source_type_counter[entity.type] += 1

            layer_details = []
            variant_notes = []
            seen_group_ids = set()
            for layer in polygon.source_layers:
                summary = layer_summaries.get(layer)
                if not summary:
                    continue
                layer_details.append(summary)
                group_id = summary.get("group_id")
                if group_id and group_id not in seen_group_ids and group_id in variant_groups_by_id:
                    seen_group_ids.add(group_id)
                    group = variant_groups_by_id[group_id]
                    if len(group["raw_layers"]) > 1:
                        variant_notes.append(
                            {
                                "group_id": group_id,
                                "group_kind": group["group_kind"],
                                "canonical_layer": group["canonical_layer"],
                                "raw_layers": group["raw_layers"],
                                "note": group["note"],
                            }
                        )

            gallery.append(
                {
                    "family": family,
                    "label": label,
                    "svg": svg_path.name,
                    "area": polygon.area,
                    "aspect_ratio": polygon.aspect_ratio,
                    "source_layers": polygon.source_layers,
                    "vertex_count": len(polygon.vertices) - 1,
                    "source_entity_count": len(polygon.source_entity_ids),
                    "source_entity_types": dict(sorted(source_type_counter.items())),
                    "layer_details": layer_details,
                    "variant_notes": variant_notes,
                    "snippets": [
                        {
                            "entity_type": entity.type,
                            "layer": entity.layer,
                            "text": entity_to_dxf_snippet(entity),
                        }
                        for entity in snippet_entities
                    ],
                }
            )
    return gallery


def build_polygon_metric_rows(polygons: Sequence[td.PolygonRecord]) -> List[List[str]]:
    rows = []
    grouped: Dict[str, List[td.PolygonRecord]] = defaultdict(list)
    for polygon in polygons:
        grouped[polygon.family].append(polygon)
    for family in ["walls", "columns", "curtain_walls"]:
        subset = grouped[family]
        area_stats = summarize_numeric([polygon.area for polygon in subset])
        aspect_stats = summarize_numeric([polygon.aspect_ratio for polygon in subset])
        vertex_stats = summarize_numeric([len(polygon.vertices) - 1 for polygon in subset])
        rows.append(
            [
                html.escape(FAMILY_LABELS[family]),
                fmt_int(len(subset)),
                fmt_float(area_stats["p50"], 1),
                fmt_float(area_stats["p75"], 1),
                fmt_float(aspect_stats["p50"], 2),
                fmt_float(aspect_stats["max"], 2),
                fmt_float(vertex_stats["p50"], 0),
            ]
        )
    return rows


def build_dashboard_html(
    summary: Dict[str, object],
    polygons: Sequence[td.PolygonRecord],
    provenance: Dict[str, object],
    gallery: Sequence[Dict[str, object]],
    output_dir: Path,
) -> str:
    entity_type_counts = list(summary["entity_type_counts"].items())[:10]
    top_layers = list(summary["top_layers"].items())[:12]
    target_totals = summary["target_primitive_totals"]
    polygon_counts = summary["polygon_counts"]
    graph_vs_direct = summary["graph_vs_direct_counts"]
    wall_snap_stats = summary["wall_snap_stats"]
    family_provenance = provenance["family_summaries"]
    layer_summaries = provenance["layer_summaries"]
    variant_groups = provenance["variant_groups"]

    grouped: Dict[str, List[td.PolygonRecord]] = defaultdict(list)
    for polygon in polygons:
        grouped[polygon.family].append(polygon)

    family_cards = "".join(
        metric_card(
            FAMILY_LABELS[family],
            fmt_int(polygon_counts[family]),
            f"median area {fmt_float(summarize_numeric([p.area for p in grouped[family]])['p50'], 1)}",
            td.FAMILY_COLORS[family],
        )
        for family in ["walls", "columns", "curtain_walls"]
    )

    main_cards = "".join(
        [
            metric_card("Runtime", f"{summary['runtime_seconds']:.2f}s", "parse + extraction + stats", "#111111"),
            metric_card("Scoped Primitives", fmt_int(target_totals["count"]), "target-layer entities", "#444444"),
            metric_card("Consumed Length", fmt_pct(target_totals["length_coverage_estimate"]), f"{fmt_float(target_totals['length_consumed'], 0)} / {fmt_float(target_totals['length_total'], 0)} units", "#0b7285"),
            metric_card("Direct vs Graph", f"{fmt_int(graph_vs_direct['direct'])} / {fmt_int(graph_vs_direct['graph_face'])}", "direct closures / graph faces", "#6c5ce7"),
        ]
    )

    provenance_cards = "".join(
        [
            metric_card("Raw Layers", fmt_int(sum(item["raw_layer_count"] for item in family_provenance.values())), "scoped target layers", "#7c4dff"),
            metric_card("Variant Groups", fmt_int(sum(item["variant_group_count"] for item in family_provenance.values())), "canonical family-layer groups", "#9c6644"),
            metric_card("Multi-Variant Groups", fmt_int(sum(item["multi_variant_group_count"] for item in family_provenance.values())), "groups with more than one raw layer", "#007f5f"),
            metric_card("Multi-Layer Polygons", fmt_int(sum(1 for polygon in polygons if len(polygon.source_layers) > 1)), "recovered tokens drawing from multiple raw layers", "#c05f00"),
        ]
    )

    family_summary_table = table_html(
        ["Family", "Polygons", "Median Area", "P75 Area", "Median Aspect", "Max Aspect", "Median Vertices"],
        build_polygon_metric_rows(polygons),
    )

    top_layer_rows = [[html.escape(layer), fmt_int(count)] for layer, count in top_layers]
    type_rows = [[html.escape(entity_type), fmt_int(count)] for entity_type, count in entity_type_counts]
    snap_rows = [
        [tol, fmt_int(stats["nodes"]), fmt_int(stats["degree_1"]), fmt_int(stats["degree_2"]), fmt_int(stats["degree_3"]), fmt_int(stats["degree_4_plus"])]
        for tol, stats in wall_snap_stats.items()
    ]

    chart_entity_types = bar_chart_svg([(label, count) for label, count in entity_type_counts], "#384bff")
    chart_top_layers = bar_chart_svg([(label, count) for label, count in top_layers], "#117a65", width=620, height=320)

    area_hists = []
    aspect_hists = []
    for family in ["walls", "columns", "curtain_walls"]:
        area_values = [math.log10(polygon.area + 1.0) for polygon in grouped[family]]
        aspect_values = [polygon.aspect_ratio for polygon in grouped[family]]
        area_hists.append(
            f"<div class='chart-card'><h3>{html.escape(FAMILY_LABELS[family])}: log10(area+1)</h3>{histogram_svg(histogram(area_values), td.FAMILY_COLORS[family])}</div>"
        )
        aspect_hists.append(
            f"<div class='chart-card'><h3>{html.escape(FAMILY_LABELS[family])}: aspect ratio</h3>{histogram_svg(histogram(aspect_values), td.FAMILY_COLORS[family])}</div>"
        )

    gallery_cards = []
    for item in gallery:
        snippets_html = "".join(
            f"<details><summary>{html.escape(snippet['entity_type'])} on {html.escape(snippet['layer'])}</summary><pre>{html.escape(snippet['text'])}</pre></details>"
            for snippet in item["snippets"]
        )
        layer_detail_html = ""
        if item["layer_details"]:
            rows = []
            for payload in item["layer_details"]:
                type_summary = ", ".join(f"{entity_type}:{count}" for entity_type, count in list(payload["entity_types"].items())[:4])
                rows.append(
                    [
                        html.escape(payload["raw_layer"]),
                        html.escape(payload["canonical_layer"]),
                        html.escape(payload["group_kind"]),
                        fmt_int(payload["entity_count"]),
                        html.escape(type_summary),
                    ]
                )
            layer_detail_html = (
                "<details><summary>Layer Provenance</summary>"
                + table_html(["Raw Layer", "Canonical", "Kind", "Count", "Types"], rows)
                + "</details>"
            )

        variant_note_html = ""
        if item["variant_notes"]:
            parts = []
            for note in item["variant_notes"]:
                parts.append(
                    f"<details><summary>{html.escape(note['canonical_layer'])} ({html.escape(note['group_kind'])})</summary>"
                    f"<p>{html.escape(note['note'])}</p>"
                    f"<p>raw layers: {html.escape(', '.join(note['raw_layers']))}</p>"
                    "</details>"
                )
            variant_note_html = "".join(parts)

        gallery_cards.append(
            "<article class='feature-card'>"
            f"<div class='feature-meta'><span class='family-chip' style='--chip:{td.FAMILY_COLORS[item['family']]}'>"
            f"{html.escape(FAMILY_LABELS[item['family']])}</span>"
            f"<h3>{html.escape(item['label'])}</h3>"
            f"<p>area {fmt_float(item['area'], 1)} | aspect {fmt_float(item['aspect_ratio'], 2)} | vertices {fmt_int(item['vertex_count'])}</p>"
            f"<p>layers: {html.escape(', '.join(item['source_layers']))}</p>"
            f"<p>source entities: {fmt_int(item['source_entity_count'])} | types: {html.escape(', '.join(f'{k}:{v}' for k, v in item['source_entity_types'].items()))}</p>"
            "</div>"
            f"<img src='dashboard_assets/{html.escape(item['svg'])}' alt='{html.escape(item['label'])} zoom'/>"
            f"<div class='feature-links'><a href='dashboard_assets/{html.escape(item['svg'])}'>SVG</a></div>"
            f"<div class='snippet-stack'>{layer_detail_html}{variant_note_html}{snippets_html}</div>"
            "</article>"
        )

    raw_code_examples = []
    for label, path in [
        ("Overlay", "extracted_overlay.svg"),
        ("Walls", "walls.svg"),
        ("Columns", "columns.svg"),
        ("Curtain Walls", "curtain_walls.svg"),
        ("Analysis Report", "analysis_report.md"),
        ("Tokenization JSON", "tokenization_output.json"),
    ]:
        raw_code_examples.append(f"<li><a href='{html.escape(path)}'>{html.escape(label)}</a></li>")

    layer_type_rows = []
    target_layer_type_counts = summary["target_layer_type_counts"]
    for layer, type_counts in list(target_layer_type_counts.items())[:18]:
        summary_text = ", ".join(f"{entity_type}:{count}" for entity_type, count in list(type_counts.items())[:4])
        layer_type_rows.append([html.escape(layer), html.escape(summary_text)])

    provenance_rows = []
    for layer, payload in sorted(layer_summaries.items(), key=lambda item: (-item[1]["entity_count"], item[0])):
        type_summary = ", ".join(f"{entity_type}:{count}" for entity_type, count in list(payload["entity_types"].items())[:4])
        provenance_rows.append(
            [
                html.escape(layer),
                html.escape(payload["canonical_layer"]),
                html.escape(FAMILY_LABELS.get(payload["family"], payload["family"])),
                fmt_int(payload["entity_count"]),
                html.escape(type_summary),
                html.escape(payload["group_kind"]),
            ]
        )

    variant_rows = []
    for group in sorted(variant_groups, key=lambda item: (item["family"], item["canonical_layer"])):
        if len(group["raw_layers"]) <= 1:
            continue
        variant_rows.append(
            [
                html.escape(FAMILY_LABELS.get(group["family"], group["family"])),
                html.escape(group["canonical_layer"]),
                html.escape(", ".join(group["raw_layers"])),
                html.escape(group["group_kind"]),
                html.escape(group["note"]),
            ]
        )

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Airport DXF Analysis Dashboard</title>
  <style>
    :root {{
      --bg: #f4f3ef;
      --panel: #ffffff;
      --ink: #171717;
      --muted: #666666;
      --line: #e5e2db;
      --shadow: 0 12px 40px rgba(22, 22, 22, 0.08);
      --radius: 18px;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: linear-gradient(180deg, #f6f4ef 0%, #efefe8 100%); color: var(--ink); }}
    a {{ color: #0e5ba8; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .page {{ width: min(96vw, 1680px); max-width: 1680px; margin: 0 auto; padding: 14px 12px 32px; }}
    .hero {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 16px;
      align-items: stretch;
      margin-bottom: 18px;
    }}
    .hero-card, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }}
    .hero-card {{ padding: 18px; }}
    .hero h1 {{ margin: 0 0 6px; font-size: 2.0rem; line-height: 1; }}
    .hero p {{ margin: 6px 0; color: var(--muted); font-size: 0.94rem; max-width: 64ch; }}
    .hero img {{
      width: 100%;
      max-height: min(280px, 42vh);
      min-height: 200px;
      object-fit: contain;
      border-radius: 16px;
      border: 1px solid var(--line);
      display: block;
      background: #fff;
    }}
    .stats-run {{
      display: grid;
      gap: 6px;
      margin-bottom: 10px;
    }}
    @media (min-width: 1400px) {{
      .stats-run--metrics {{
        grid-template-columns: repeat(7, minmax(0, 1fr));
      }}
      .stats-run--metrics .metric-grid,
      .stats-run--metrics .family-strip {{
        display: contents;
      }}
      .stats-run--prov {{
        grid-template-columns: repeat(4, minmax(0, 1fr));
      }}
      .stats-run--prov .metric-grid {{
        display: contents;
      }}
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 6px;
      margin-bottom: 8px;
    }}
    .metric-card {{
      padding: 9px 11px 10px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, #ffffff 0%, #fbfbfb 100%);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.4);
      position: relative;
      overflow: hidden;
    }}
    .metric-card::before {{
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 3px;
      background: var(--accent);
    }}
    .metric-title {{ font-size: 0.78rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; line-height: 1.2; }}
    .metric-value {{ font-size: 1.32rem; margin: 4px 0 2px; font-weight: 700; line-height: 1.15; }}
    .metric-detail {{ color: var(--muted); font-size: 0.78rem; line-height: 1.28; }}
    .family-strip {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 6px;
      margin-bottom: 0;
    }}
    .section-title {{
      margin: 22px 0 10px;
      font-size: 1.28rem;
      line-height: 1.1;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: 1.08fr 0.92fr;
      gap: 14px;
      margin-bottom: 14px;
    }}
    .panel {{ padding: 16px; }}
    .panel h2, .panel h3 {{ margin-top: 0; }}
    .chart-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 14px;
      align-items: start;
    }}
    .chart-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 16px;
    }}
    .chart-card h3 {{ margin: 0 0 10px; font-size: 1rem; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.94rem;
    }}
    th, td {{
      text-align: left;
      padding: 9px 8px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-size: 0.84rem; text-transform: uppercase; letter-spacing: 0.04em; }}
    .feature-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      align-items: start;
    }}
    .feature-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 14px;
    }}
    .feature-card img {{
      width: 100%;
      display: block;
      border-radius: 14px;
      border: 1px solid var(--line);
      margin: 10px 0 6px;
      background: #fff;
    }}
    .feature-meta h3 {{ margin: 4px 0; font-size: 1rem; }}
    .feature-meta p {{ margin: 4px 0; color: var(--muted); font-size: 0.88rem; }}
    .family-chip {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      background: color-mix(in srgb, var(--chip) 14%, white);
      color: #222;
      border: 1px solid color-mix(in srgb, var(--chip) 30%, white);
      font-size: 0.8rem;
      font-weight: 700;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }}
    .feature-links {{ display: flex; gap: 12px; margin: 2px 0 8px; font-size: 0.88rem; }}
    details {{
      border-top: 1px solid var(--line);
      padding-top: 8px;
      margin-top: 8px;
    }}
    summary {{
      cursor: pointer;
      font-weight: 600;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: #fbfbfd;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      overflow: auto;
      font-size: 0.8rem;
      line-height: 1.3;
    }}
    .note {{
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.38;
    }}
    .chart-svg {{ width: 100%; height: auto; display: block; }}
    .file-list {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px 16px;
      padding-left: 18px;
    }}
    @media (max-width: 1700px) {{
      .feature-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    }}
    @media (max-width: 1360px) {{
      .feature-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 1400px) {{
      .chart-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .metric-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .family-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 1100px) {{
      .hero, .two-col, .chart-grid, .feature-grid, .metric-grid, .family-strip {{
        grid-template-columns: 1fr;
      }}
      .file-list {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="hero-card">
        <h1>Airport DXF Analysis Dashboard</h1>
        <p>This dashboard turns the mezzanine DXF into something you can read like a data system instead of a flat CAD dump: raw primitive mix, closure-driven tokenization, family geometry distributions, representative zoom panels, and snippets of DXF code from the recovered features.</p>
        <p>The key pattern is visible in the stats and the images: columns are mostly direct closed carriers, curtain walls are regular local panels, and walls are the hard case because they need graph closure across fragmented linework.</p>
      </div>
      <div class="hero-card">
        <img src="extracted_overlay.svg" alt="Overlay preview">
      </div>
    </section>

    <section class="stats-run stats-run--metrics">
      <div class="metric-grid">{main_cards}</div>
      <div class="family-strip">{family_cards}</div>
    </section>

    <h2 class="section-title">Provenance</h2>
    <section class="stats-run stats-run--prov">
      <div class="metric-grid">{provenance_cards}</div>
    </section>

    <h2 class="section-title">Representative Feature Zooms</h2>
    <section class="feature-grid">
      {''.join(gallery_cards)}
    </section>

    <h2 class="section-title">Raw File Mix</h2>
    <section class="two-col">
      <div class="panel">
        <h3>Entity Type Counts</h3>
        {chart_entity_types}
        <div class="note">The file is overwhelmingly line-driven. That matters because line-heavy wall layers force composition through endpoint closure instead of direct extraction.</div>
      </div>
      <div class="panel">
        <h3>Top Layers</h3>
        {chart_top_layers}
        <div class="note">These are counts, not semantic certainty. Layer names act as class hints, not instance identity.</div>
      </div>
    </section>

    <section class="two-col">
      <div class="panel">
        <h3>Top Entity Types Table</h3>
        {table_html(["Entity Type", "Count"], type_rows)}
      </div>
      <div class="panel">
        <h3>Top Layers Table</h3>
        {table_html(["Layer", "Count"], top_layer_rows)}
      </div>
    </section>

    <h2 class="section-title">Tokenization And Geometry</h2>
    <section class="two-col">
      <div class="panel">
        <h3>Polygon Family Summary</h3>
        {family_summary_table}
      </div>
      <div class="panel">
        <h3>Wall Snap Connectivity</h3>
        {table_html(["Tolerance", "Nodes", "Degree-1", "Degree-2", "Degree-3", "Degree-4+"], snap_rows)}
        <p class="note">The degree-4+ junction load is the tell. Once snapping is applied, walls become a high-branching graph rather than a simple rectangle list.</p>
      </div>
    </section>

    <section class="chart-grid">
      {''.join(area_hists)}
    </section>
    <section class="chart-grid">
      {''.join(aspect_hists)}
    </section>

    <h2 class="section-title">Scoped Layer Structure</h2>
    <section class="panel">
      <h3>Target Layer / Primitive Mix</h3>
      {table_html(["Layer", "Observed Primitive Types"], layer_type_rows)}
    </section>

    <section class="two-col">
      <div class="panel">
        <h3>Raw Layer Provenance</h3>
        {table_html(["Raw Layer", "Canonical Layer", "Family", "Count", "Types", "Group Kind"], provenance_rows[:28])}
      </div>
      <div class="panel">
        <h3>Canonical Variant Groups</h3>
        {table_html(["Family", "Canonical Layer", "Raw Layers", "Kind", "Note"], variant_rows[:18])}
      </div>
    </section>

    <h2 class="section-title">Linked Artifacts</h2>
    <section class="panel">
      <h3>Open The Generated Files</h3>
      <ul class="file-list">
        {''.join(raw_code_examples)}
      </ul>
      <p class="note">Dashboard feature images live under <code>dashboard_assets/</code>. The SVGs are the source assets for feature zooms and provenance inspection.</p>
    </section>
  </main>
</body>
</html>
"""
    return html_text


def build_dashboard(input_dxf: Path, output_dir: Path, snap_tolerance: float, extraction=None) -> None:
    from . import dataset as _ds

    analysis = _ds.build(input_dxf, snap_tolerance, extraction=extraction)
    render_dashboard(analysis, output_dir)


def render_dashboard(analysis, output_dir: Path) -> None:
    """Pure renderer over an AnalysisDataset.

    Kept separate from the CLI entry point so the REPL can call it directly.
    """
    gallery = collect_representative_assets(
        analysis.entities, analysis.polygons, analysis.provenance, output_dir
    )
    dashboard_html = build_dashboard_html(
        analysis.summary, analysis.polygons, analysis.provenance, gallery, output_dir
    )
    (output_dir / "dashboard.html").write_text(dashboard_html, encoding="utf-8")
    (output_dir / "dashboard_assets" / "dashboard_data.json").write_text(
        json.dumps(
            {"summary": analysis.summary, "provenance": analysis.provenance, "gallery": gallery},
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "dashboard_assets" / "provenance_summary.json").write_text(
        json.dumps(analysis.provenance, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an HTML dashboard for the DXF analysis outputs.")
    parser.add_argument("input_dxf", type=Path, help="Source DXF file.")
    parser.add_argument("output_dir", type=Path, help="Directory where dashboard.html and dashboard_assets will be written.")
    parser.add_argument("--snap-tolerance", type=float, default=0.5, help="Snap tolerance used for graph-face extraction.")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    build_dashboard(args.input_dxf, args.output_dir, args.snap_tolerance)


if __name__ == "__main__":
    main()
