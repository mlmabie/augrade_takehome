"""Merge-candidate scoring, family presets, and polygon descriptors.

Pure-compute layer extracted from the old ``build_merge_lab.py`` so the
dataset builder, HTML renderers, and REPL can all share one implementation.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Dict, Sequence

import tokenize_dxf as td

from .geometry import (
    angle_diff_degrees,
    averaged_orientation,
    bbox_gap,
    bbox_iou,
    distance,
    dominant_orientation,
    entity_to_dxf_snippet,
    equivalent_radius,
    interval_gap,
    interval_overlap_ratio,
    layer_jaccard,
    polygon_centroid,
    polygon_perimeter,
    projection_interval,
    ring_boundary_gap,
)


FAMILY_LABELS = {
    "walls": "Walls",
    "columns": "Columns",
    "curtain_walls": "Curtain Walls",
}

FAMILY_PRESETS: Dict[str, Dict[str, float]] = {
    "walls": {
        "candidate_bbox_gap": 220.0,
        "max_boundary_gap": 48.0,
        "max_angle_diff": 18.0,
        "max_thickness_rel": 0.75,
        "max_area_ratio": 6.0,
        "max_gap_major_norm": 6.0,
        "max_gap_minor_norm": 1.6,
        "min_overlap_major": 0.0,
        "min_overlap_minor": 0.35,
        "score_threshold": 1.6,
        "w_gap": 1.6,
        "w_angle": 0.9,
        "w_thickness": 1.2,
        "w_continuity": 1.1,
        "w_alignment": 1.3,
        "w_iou": 0.2,
        "w_layer": 0.3,
        "w_memory": 0.8,
        "memory_beta": 8.0,
    },
    "columns": {
        "candidate_bbox_gap": 120.0,
        "max_boundary_gap": 36.0,
        "max_angle_diff": 90.0,
        "max_thickness_rel": 1.0,
        "max_area_ratio": 3.5,
        "max_gap_major_norm": 1.5,
        "max_gap_minor_norm": 1.5,
        "min_overlap_major": 0.0,
        "min_overlap_minor": 0.0,
        "score_threshold": 1.3,
        "w_gap": 1.7,
        "w_angle": 0.0,
        "w_thickness": 1.2,
        "w_continuity": 0.4,
        "w_alignment": 0.5,
        "w_iou": 1.1,
        "w_layer": 0.3,
        "w_memory": 0.9,
        "memory_beta": 8.0,
    },
    "curtain_walls": {
        "candidate_bbox_gap": 120.0,
        "max_boundary_gap": 28.0,
        "max_angle_diff": 14.0,
        "max_thickness_rel": 1.2,
        "max_area_ratio": 8.0,
        "max_gap_major_norm": 2.4,
        "max_gap_minor_norm": 1.2,
        "min_overlap_major": 0.0,
        "min_overlap_minor": 0.0,
        "score_threshold": 1.2,
        "w_gap": 1.2,
        "w_angle": 1.2,
        "w_thickness": 0.9,
        "w_continuity": 1.3,
        "w_alignment": 1.0,
        "w_iou": 0.5,
        "w_layer": 0.3,
        "w_memory": 0.8,
        "memory_beta": 8.0,
    },
}

FAMILY_NOTES = {
    "walls": "Walls should usually merge by thickness-consistent continuity or overlap, not by raw proximity alone.",
    "columns": "Columns mostly want deduplication and concentric grouping, so center and size agreement matter more than orientation.",
    "curtain_walls": "Curtain wall panels often want local grouping while preserving grid structure, so continuity and size regularity matter more than unioning everything.",
}

from tokenize_dxf import FAMILY_ID_FALLBACK as ID_PREFIX


def polygon_descriptor(
    polygon: td.PolygonRecord,
    family_local_index: int,
    entity_by_id: Dict[str, td.Entity],
    provenance: Dict[str, object],
    *,
    snippet_max_lines: int = 38,
) -> Dict[str, object]:
    points = [(round(x, 4), round(y, 4)) for x, y in polygon.vertices]
    centroid = polygon_centroid(points)
    perimeter = polygon_perimeter(points)
    orientation = dominant_orientation(points)
    major_interval = projection_interval(points, orientation)
    minor_interval = projection_interval(points, orientation + math.pi / 2.0)
    span = max(
        major_interval[1] - major_interval[0],
        minor_interval[1] - minor_interval[0],
    )
    thickness = min(
        major_interval[1] - major_interval[0],
        minor_interval[1] - minor_interval[0],
    )
    compactness = 4 * math.pi * polygon.area / max(perimeter * perimeter, 1e-9)

    snippet_entities = []
    priority = {"CIRCLE": 0, "ARC": 1, "LINE": 2, "LWPOLYLINE": 3, "POLYLINE": 4, "ELLIPSE": 5}
    for entity_id in sorted(
        polygon.source_entity_ids,
        key=lambda item: priority.get(entity_by_id[item].type, 99) if item in entity_by_id else 99,
    ):
        if entity_id in entity_by_id:
            snippet_entities.append(entity_by_id[entity_id])
        if len(snippet_entities) >= 2:
            break

    source_type_counter: Counter = Counter()
    for entity_id in polygon.source_entity_ids:
        entity = entity_by_id.get(entity_id)
        if entity is not None:
            source_type_counter[entity.type] += 1

    layer_summaries = provenance["layer_summaries"]
    variant_groups_by_id = provenance["variant_groups_by_id"]
    source_layer_details = []
    source_variant_groups = []
    seen_group_ids = set()
    for layer in polygon.source_layers:
        summary = layer_summaries.get(layer)
        if summary is None:
            continue
        source_layer_details.append(summary)
        group_id = summary.get("group_id")
        if group_id and group_id not in seen_group_ids and group_id in variant_groups_by_id:
            seen_group_ids.add(group_id)
            group = variant_groups_by_id[group_id]
            if len(group["raw_layers"]) > 1:
                source_variant_groups.append(group)

    id_prefix = ID_PREFIX[polygon.family]
    return {
        "local_index": family_local_index,
        "id": f"{id_prefix}_{family_local_index + 1:04d}",
        "family": polygon.family,
        "bbox": [round(v, 4) for v in polygon.bbox],
        "centroid": [round(centroid[0], 4), round(centroid[1], 4)],
        "area": round(polygon.area, 4),
        "perimeter": round(perimeter, 4),
        "aspect_ratio": round(polygon.aspect_ratio, 4),
        "orientation_deg": round(math.degrees(orientation), 4),
        "span": round(span, 4),
        "thickness": round(max(thickness, 1e-6), 4),
        "compactness": round(compactness, 6),
        "source_layers": polygon.source_layers,
        "source_kind": polygon.source_kind,
        "source_entity_count": len(polygon.source_entity_ids),
        "source_entity_types": dict(sorted(source_type_counter.items())),
        "source_layer_details": source_layer_details,
        "source_variant_groups": source_variant_groups,
        "vertices": [[round(x, 4), round(y, 4)] for x, y in points],
        "snippets": [
            {
                "entity_type": entity.type,
                "layer": entity.layer,
                "text": entity_to_dxf_snippet(entity, max_lines=snippet_max_lines),
            }
            for entity in snippet_entities
        ],
    }


def candidate_pair(a: Dict[str, object], b: Dict[str, object]) -> Dict[str, float]:
    ring_a = [(x, y) for x, y in a["vertices"]]
    ring_b = [(x, y) for x, y in b["vertices"]]
    bbox_a = tuple(a["bbox"])
    bbox_b = tuple(b["bbox"])
    theta_a = math.radians(a["orientation_deg"])
    theta_b = math.radians(b["orientation_deg"])
    theta = averaged_orientation(theta_a, theta_b)

    major_a = projection_interval(ring_a, theta)
    major_b = projection_interval(ring_b, theta)
    minor_a = projection_interval(ring_a, theta + math.pi / 2.0)
    minor_b = projection_interval(ring_b, theta + math.pi / 2.0)

    boundary_gap = ring_boundary_gap(ring_a, ring_b)
    center_gap = distance(tuple(a["centroid"]), tuple(b["centroid"]))
    major_gap = interval_gap(major_a, major_b)
    minor_gap = interval_gap(minor_a, minor_b)
    major_overlap = interval_overlap_ratio(major_a, major_b)
    minor_overlap = interval_overlap_ratio(minor_a, minor_b)
    thickness_ref = max(1.0, min(a["thickness"], b["thickness"]))
    radius_ref = max(1.0, min(equivalent_radius(a["area"]), equivalent_radius(b["area"])))
    scale_ref = radius_ref if a["family"] == "columns" else thickness_ref

    return {
        "bbox_gap": bbox_gap(bbox_a, bbox_b),
        "boundary_gap": boundary_gap,
        "center_gap": center_gap,
        "angle_diff_deg": angle_diff_degrees(theta_a, theta_b),
        "thickness_rel_diff": abs(a["thickness"] - b["thickness"]) / thickness_ref,
        "area_ratio": max(a["area"], b["area"]) / max(min(a["area"], b["area"]), 1e-6),
        "span_ratio": max(a["span"], b["span"]) / max(min(a["span"], b["span"]), 1e-6),
        "gap_major_norm": major_gap / scale_ref,
        "gap_minor_norm": minor_gap / scale_ref,
        "overlap_major_ratio": major_overlap,
        "overlap_minor_ratio": minor_overlap,
        "bbox_iou": bbox_iou(bbox_a, bbox_b),
        "layer_jaccard": layer_jaccard(a["source_layers"], b["source_layers"]),
        "same_source_kind": 1.0 if a["source_kind"] == b["source_kind"] else 0.0,
        "scale_ref": scale_ref,
    }


def heuristic_score(family: str, metrics: Dict[str, float], preset: Dict[str, float]) -> float:
    def smaller_is_better(value: float, max_value: float) -> float:
        if max_value <= 1e-9:
            return 0.0
        return max(-0.5, 1.0 - value / max_value)

    def larger_is_better(value: float, min_value: float) -> float:
        if min_value >= 1.0:
            return value
        return max(-0.5, (value - min_value) / max(1e-9, 1.0 - min_value))

    score = 0.0
    score += preset["w_gap"] * smaller_is_better(metrics["boundary_gap"], preset["max_boundary_gap"])
    score += preset["w_angle"] * smaller_is_better(metrics["angle_diff_deg"], preset["max_angle_diff"])
    score += preset["w_thickness"] * smaller_is_better(metrics["thickness_rel_diff"], preset["max_thickness_rel"])
    score += preset["w_continuity"] * (
        0.65 * smaller_is_better(metrics["gap_major_norm"], preset["max_gap_major_norm"])
        + 0.35 * larger_is_better(metrics["overlap_major_ratio"], preset["min_overlap_major"])
    )
    score += preset["w_alignment"] * (
        0.65 * smaller_is_better(metrics["gap_minor_norm"], preset["max_gap_minor_norm"])
        + 0.35 * larger_is_better(metrics["overlap_minor_ratio"], preset["min_overlap_minor"])
    )
    score += preset["w_iou"] * metrics["bbox_iou"]
    score += preset["w_layer"] * metrics["layer_jaccard"]
    return score


def hard_pass(metrics: Dict[str, float], preset: Dict[str, float]) -> bool:
    return (
        metrics["boundary_gap"] <= preset["max_boundary_gap"]
        and metrics["angle_diff_deg"] <= preset["max_angle_diff"]
        and metrics["thickness_rel_diff"] <= preset["max_thickness_rel"]
        and metrics["area_ratio"] <= preset["max_area_ratio"]
        and metrics["gap_major_norm"] <= preset["max_gap_major_norm"]
        and metrics["gap_minor_norm"] <= preset["max_gap_minor_norm"]
        and metrics["overlap_major_ratio"] >= preset["min_overlap_major"]
        and metrics["overlap_minor_ratio"] >= preset["min_overlap_minor"]
    )


def generate_family_data(
    family: str,
    polygons: Sequence[td.PolygonRecord],
    entity_by_id: Dict[str, td.Entity],
    provenance: Dict[str, object],
) -> Dict[str, object]:
    preset = FAMILY_PRESETS[family]
    descriptors = [
        polygon_descriptor(polygon, idx, entity_by_id, provenance)
        for idx, polygon in enumerate(polygons)
    ]
    candidates = []
    for idx in range(len(descriptors)):
        for jdx in range(idx + 1, len(descriptors)):
            a = descriptors[idx]
            b = descriptors[jdx]
            if bbox_gap(tuple(a["bbox"]), tuple(b["bbox"])) > preset["candidate_bbox_gap"]:
                continue
            metrics = candidate_pair(a, b)
            metrics["heuristic_score"] = heuristic_score(family, metrics, preset)
            metrics["hard_pass"] = 1 if hard_pass(metrics, preset) else 0
            metrics["recommended"] = (
                1
                if metrics["hard_pass"] and metrics["heuristic_score"] >= preset["score_threshold"]
                else 0
            )
            candidates.append(
                {
                    "id": f"{family}:{idx}:{jdx}",
                    "a": idx,
                    "b": jdx,
                    **{
                        key: round(value, 6) if isinstance(value, float) else value
                        for key, value in metrics.items()
                    },
                }
            )

    recommended = sum(candidate["recommended"] for candidate in candidates)
    return {
        "family": family,
        "note": FAMILY_NOTES[family],
        "preset": preset,
        "polygons": descriptors,
        "provenance": {
            "family_summary": provenance["family_summaries"][family],
            "layer_summaries": [
                payload
                for payload in provenance["layer_summaries"].values()
                if payload["family"] == family
            ],
            "variant_groups": [
                payload
                for payload in provenance["variant_groups"]
                if payload["family"] == family
            ],
        },
        "candidates": candidates,
        "stats": {
            "polygon_count": len(descriptors),
            "candidate_count": len(candidates),
            "recommended_count": recommended,
        },
    }
