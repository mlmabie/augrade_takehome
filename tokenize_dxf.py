#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple, Union


Point = Tuple[float, float]


# The flagless/default run uses conservative=0.5 and matches the checked-in
# out/ bundle. The liberal preset and --snap-tolerance forms are retained for
# audit/debug sweeps, not as alternate submission outputs.
SNAP_TOLERANCE_MODES: Dict[str, float] = {
    "conservative": 0.5,
    "liberal": 0.75,
}


FAMILY_LAYER_MAP = {
    "walls": {
        "A-EXTERNAL WALL",
        "A-EXTERNAL WALL HATCH",
        "A-MEZZANINE WALL FULL",
        "A-MEZZANINE WALL FULL HATCH",
        "A-WALL 1",
        "A-WALL 1 HATCH",
        "A-WALL 2",
        "A-WALL 2 HATCH",
        "A-PARTITION WALL",
        "A-WALL PARAPET",
        "A-WALL NICHE",
        "A-MEZZANINE WALL FINISH",
        "A-WALL PANEL",
        "S-CONCRETE WALL",
    },
    "columns": {
        "S-STEEL POST",
        "S-STEEL COLUMN",
        "S-STEEL COLUMN HATCH",
        "S-COLUMN",
        "S-COLUMN HATCH",
        "S-CONCRETE COLUMN",
        "S-CONCRETE COLUMN HATCH",
        "S-COLUMN PROTECTION",
    },
    "curtain_walls": {
        "A-GLAZING MULLION",
        "A-GLAZING-MULLION",
        "A-GLAZING FULL",
        "A-GLAZING-FULL",
        "A-GLAZING INTERNAL",
        "A-GLAZING ARRAY",
        "A-GLAZING SILL",
        "A-WALL SILL",
        "A-EXTERNAL GLASS",
        "A-INTERNAL GLASS",
    },
}

CANONICAL_FAMILY_LAYERS = {
    family: {re.sub(r"[-\s]+", " ", layer.upper()).strip() for layer in layers}
    for family, layers in FAMILY_LAYER_MAP.items()
}

# AIA-grammar-aware polygon ID prefixes; companion HATCH layers keep distinct
# prefixes so provenance remains visible in generated IDs.
LAYER_ID_PREFIX: Dict[str, str] = {
    "A-EXTERNAL WALL":          "a_wall_ext",
    "A-EXTERNAL WALL HATCH":    "a_wall_ext_hatch",
    "A-MEZZANINE WALL FULL":    "a_wall_mezz_full",
    "A-MEZZANINE WALL FULL HATCH": "a_wall_mezz_full_hatch",
    "A-MEZZANINE WALL FINISH":  "a_wall_mezz_fin",
    "A-WALL 1":                 "a_wall_v1",
    "A-WALL 1 HATCH":           "a_wall_v1_hatch",
    "A-WALL 2":                 "a_wall_v2",
    "A-WALL 2 HATCH":           "a_wall_v2_hatch",
    "A-PARTITION WALL":         "a_wall_part",
    "A-WALL PARAPET":           "a_wall_parapet",
    "A-WALL NICHE":             "a_wall_niche",
    "A-WALL PANEL":             "a_wall_panel",
    "S-CONCRETE WALL":          "s_wall_conc",
    "S-STEEL POST":             "s_post_steel",
    "S-STEEL COLUMN":           "s_col_steel",
    "S-STEEL COLUMN HATCH":     "s_col_steel_hatch",
    "S-COLUMN":                 "s_col",
    "S-COLUMN HATCH":           "s_col_hatch",
    "S-CONCRETE COLUMN":        "s_col_conc",
    "S-CONCRETE COLUMN HATCH": "s_col_conc_hatch",
    "S-COLUMN PROTECTION":      "s_col_prot",
    "A-GLAZING MULLION":        "a_glaz_mull",
    "A-GLAZING-MULLION":        "a_glaz_mull",
    "A-GLAZING FULL":           "a_glaz_full",
    "A-GLAZING-FULL":           "a_glaz_full",
    "A-GLAZING INTERNAL":       "a_glaz_int",
    "A-GLAZING ARRAY":          "a_glaz_array",
    "A-GLAZING SILL":           "a_glaz_sill",
    "A-WALL SILL":              "a_sill_wall",
    "A-EXTERNAL GLASS":         "a_glass_ext",
    "A-INTERNAL GLASS":         "a_glass_int",
}

FAMILY_ID_FALLBACK: Dict[str, str] = {
    "walls": "wall",
    "columns": "col",
    "curtain_walls": "cw",
}

FAMILY_COLORS = {
    "walls": "#2f5bff",
    "columns": "#d9342b",
    "curtain_walls": "#1b9e5a",
}


HATCH_PATH_EXTERNAL = 1
HATCH_PATH_POLYLINE = 2
HATCH_PATH_OUTERMOST = 16


@dataclass
class HatchBoundaryPath:
    flags: int
    points: List[Point]

    @property
    def is_outer_candidate(self) -> bool:
        return bool(self.flags & (HATCH_PATH_EXTERNAL | HATCH_PATH_OUTERMOST))


@dataclass
class Entity:
    entity_id: str
    type: str
    layer: str
    family: Optional[str]
    tags: List[Tuple[int, str]] = field(default_factory=list)
    closed: bool = False
    points: List[Tuple[float, float, float]] = field(default_factory=list)
    start: Optional[Point] = None
    end: Optional[Point] = None
    center: Optional[Point] = None
    radius: Optional[float] = None
    start_angle: Optional[float] = None
    end_angle: Optional[float] = None
    major_axis: Optional[Point] = None
    ratio: Optional[float] = None
    start_param: Optional[float] = None
    end_param: Optional[float] = None
    hatch_paths: List[HatchBoundaryPath] = field(default_factory=list)


@dataclass
class Segment:
    family: str
    layer: str
    entity_id: str
    start: Point
    end: Point


@dataclass
class PolygonRecord:
    family: str
    vertices: List[Point]
    source_layers: List[str]
    source_entity_ids: List[str]
    source_kind: str
    area: float
    bbox: Tuple[float, float, float, float]
    aspect_ratio: float


def canonical_layer_name(layer: str) -> str:
    return re.sub(r"[-\s]+", " ", layer.upper()).strip()


def infer_family(layer: str) -> Optional[str]:
    canonical = canonical_layer_name(layer)
    for family, layers in CANONICAL_FAMILY_LAYERS.items():
        if canonical in layers:
            return family
    return None


def read_dxf_pairs(path: Path) -> Iterator[Tuple[int, str]]:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        while True:
            code = handle.readline()
            if not code:
                break
            value = handle.readline()
            if not value:
                break
            yield int(code.strip() or 0), value.rstrip("\r\n")


def parse_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except ValueError:
        return default


def parse_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except ValueError:
        return default


def parse_lwpolyline_points(tags: Sequence[Tuple[int, str]]) -> List[Tuple[float, float, float]]:
    points: List[Tuple[float, float, float]] = []
    x_value: Optional[float] = None
    y_value: Optional[float] = None
    bulge = 0.0

    def flush_current() -> None:
        nonlocal x_value, y_value, bulge
        if x_value is not None and y_value is not None:
            points.append((x_value, y_value, bulge))
        x_value = None
        y_value = None
        bulge = 0.0

    for code, raw in tags:
        if code == 10:
            flush_current()
            x_value = parse_float(raw)
        elif code == 20:
            y_value = parse_float(raw)
        elif code == 42:
            bulge = parse_float(raw)
    flush_current()
    return points


def finalize_entity(entity_id: str, entity_type: str, tags: Sequence[Tuple[int, str]]) -> Entity:
    layer = ""
    for code, raw in tags:
        if code == 8:
            layer = raw
            break

    entity = Entity(
        entity_id=entity_id,
        type=entity_type,
        layer=layer,
        family=infer_family(layer),
        tags=list(tags),
    )

    if entity_type == "LINE":
        x1 = y1 = x2 = y2 = None
        for code, raw in tags:
            if code == 10:
                x1 = parse_float(raw)
            elif code == 20:
                y1 = parse_float(raw)
            elif code == 11:
                x2 = parse_float(raw)
            elif code == 21:
                y2 = parse_float(raw)
        if None not in (x1, y1, x2, y2):
            entity.start = (x1, y1)
            entity.end = (x2, y2)

    elif entity_type == "ARC":
        cx = cy = radius = start_angle = end_angle = None
        for code, raw in tags:
            if code == 10:
                cx = parse_float(raw)
            elif code == 20:
                cy = parse_float(raw)
            elif code == 40:
                radius = parse_float(raw)
            elif code == 50:
                start_angle = parse_float(raw)
            elif code == 51:
                end_angle = parse_float(raw)
        if None not in (cx, cy, radius, start_angle, end_angle):
            entity.center = (cx, cy)
            entity.radius = radius
            entity.start_angle = start_angle
            entity.end_angle = end_angle

    elif entity_type == "CIRCLE":
        cx = cy = radius = None
        for code, raw in tags:
            if code == 10:
                cx = parse_float(raw)
            elif code == 20:
                cy = parse_float(raw)
            elif code == 40:
                radius = parse_float(raw)
        if None not in (cx, cy, radius):
            entity.center = (cx, cy)
            entity.radius = radius
            entity.closed = True

    elif entity_type == "ELLIPSE":
        cx = cy = mx = my = ratio = start_param = end_param = None
        for code, raw in tags:
            if code == 10:
                cx = parse_float(raw)
            elif code == 20:
                cy = parse_float(raw)
            elif code == 11:
                mx = parse_float(raw)
            elif code == 21:
                my = parse_float(raw)
            elif code == 40:
                ratio = parse_float(raw)
            elif code == 41:
                start_param = parse_float(raw)
            elif code == 42:
                end_param = parse_float(raw)
        if None not in (cx, cy, mx, my, ratio, start_param, end_param):
            entity.center = (cx, cy)
            entity.major_axis = (mx, my)
            entity.ratio = ratio
            entity.start_param = start_param
            entity.end_param = end_param
            sweep = normalized_param_sweep(start_param, end_param)
            entity.closed = abs(sweep - 2 * math.pi) < 1e-3

    elif entity_type == "LWPOLYLINE":
        flags = 0
        for code, raw in tags:
            if code == 70:
                flags = parse_int(raw)
                break
        entity.points = parse_lwpolyline_points(tags)
        entity.closed = bool(flags & 1) or polyline_is_closed([(x, y) for x, y, _ in entity.points])

    elif entity_type == "HATCH":
        entity.hatch_paths = parse_hatch_boundary_paths(tags)
        entity.closed = bool(entity.hatch_paths)

    return entity


def finalize_polyline_entity(entity_id: str, header_tags: Sequence[Tuple[int, str]], vertex_tags: Sequence[Sequence[Tuple[int, str]]]) -> Entity:
    tags = list(header_tags)
    layer = ""
    flags = 0
    for code, raw in header_tags:
        if code == 8:
            layer = raw
        elif code == 70:
            flags = parse_int(raw)

    points: List[Tuple[float, float, float]] = []
    for vertex in vertex_tags:
        x_value = None
        y_value = None
        bulge = 0.0
        for code, raw in vertex:
            if code == 10:
                x_value = parse_float(raw)
            elif code == 20:
                y_value = parse_float(raw)
            elif code == 42:
                bulge = parse_float(raw)
        if x_value is not None and y_value is not None:
            points.append((x_value, y_value, bulge))

    return Entity(
        entity_id=entity_id,
        type="POLYLINE",
        layer=layer,
        family=infer_family(layer),
        tags=tags,
        points=points,
        closed=bool(flags & 1) or polyline_is_closed([(x, y) for x, y, _ in points]),
    )


def iter_entities(path: Path) -> Iterator[Entity]:
    in_entities = False
    current_type: Optional[str] = None
    current_tags: List[Tuple[int, str]] = []
    entity_index = 0

    polyline_header: Optional[List[Tuple[int, str]]] = None
    polyline_vertices: List[List[Tuple[int, str]]] = []
    active_vertex: Optional[List[Tuple[int, str]]] = None

    def next_entity_id() -> str:
        nonlocal entity_index
        entity_index += 1
        return f"e_{entity_index:06d}"

    def flush_current_entity() -> Optional[Entity]:
        nonlocal current_type, current_tags
        if current_type is None:
            return None
        entity = finalize_entity(next_entity_id(), current_type, current_tags)
        current_type = None
        current_tags = []
        return entity

    for code, raw in read_dxf_pairs(path):
        if not in_entities:
            if code == 2 and raw == "ENTITIES":
                in_entities = True
            continue

        if polyline_header is not None:
            if code == 0 and raw == "VERTEX":
                if active_vertex is not None:
                    polyline_vertices.append(active_vertex)
                active_vertex = []
                continue
            if code == 0 and raw == "SEQEND":
                if active_vertex is not None:
                    polyline_vertices.append(active_vertex)
                yield finalize_polyline_entity(next_entity_id(), polyline_header, polyline_vertices)
                polyline_header = None
                polyline_vertices = []
                active_vertex = None
                continue
            if code == 0 and raw == "ENDSEC":
                if active_vertex is not None:
                    polyline_vertices.append(active_vertex)
                yield finalize_polyline_entity(next_entity_id(), polyline_header, polyline_vertices)
                break
            if code == 0:
                if active_vertex is not None:
                    polyline_vertices.append(active_vertex)
                yield finalize_polyline_entity(next_entity_id(), polyline_header, polyline_vertices)
                polyline_header = None
                polyline_vertices = []
                active_vertex = None
                current_type = raw
                current_tags = []
                continue
            if active_vertex is not None:
                active_vertex.append((code, raw))
            else:
                polyline_header.append((code, raw))
            continue

        if code == 0 and raw == "ENDSEC":
            entity = flush_current_entity()
            if entity is not None:
                yield entity
            break

        if code == 0:
            entity = flush_current_entity()
            if entity is not None:
                yield entity
            if raw == "POLYLINE":
                polyline_header = []
                polyline_vertices = []
                active_vertex = None
            else:
                current_type = raw
                current_tags = []
            continue

        if current_type is not None:
            current_tags.append((code, raw))


def normalized_param_sweep(start_param: float, end_param: float) -> float:
    sweep = end_param - start_param
    while sweep <= 0:
        sweep += 2 * math.pi
    return sweep


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def polyline_is_closed(points: Sequence[Point], tolerance: float = 1e-6) -> bool:
    if len(points) < 3:
        return False
    return distance(points[0], points[-1]) <= tolerance


def close_ring(points: Sequence[Point], tolerance: float = 1e-6) -> List[Point]:
    cleaned = dedupe_consecutive(points, tolerance=tolerance)
    if len(cleaned) < 3:
        return []
    if distance(cleaned[0], cleaned[-1]) > tolerance:
        cleaned.append(cleaned[0])
    return cleaned


def dedupe_consecutive(points: Sequence[Point], tolerance: float = 1e-6) -> List[Point]:
    output: List[Point] = []
    for point in points:
        if not output or distance(output[-1], point) > tolerance:
            output.append(point)
    if len(output) > 1 and distance(output[0], output[-1]) <= tolerance:
        output[-1] = output[0]
    return output


def polygon_area(points: Sequence[Point]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for index in range(len(points) - 1):
        x1, y1 = points[index]
        x2, y2 = points[index + 1]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def polygon_bbox(points: Sequence[Point]) -> Tuple[float, float, float, float]:
    xs = [point[0] for point in points[:-1]]
    ys = [point[1] for point in points[:-1]]
    return min(xs), min(ys), max(xs), max(ys)


def aspect_ratio_from_bbox(bbox: Tuple[float, float, float, float]) -> float:
    min_x, min_y, max_x, max_y = bbox
    width = max_x - min_x
    height = max_y - min_y
    minor = max(min(width, height), 1e-9)
    major = max(width, height)
    return major / minor


def ensure_clockwise(points: Sequence[Point]) -> List[Point]:
    ring = close_ring(points)
    if not ring:
        return []
    if polygon_area(ring) > 0:
        body = list(reversed(ring[:-1]))
        body.append(body[0])
        return body
    return ring


def rotate_canonical(points: Sequence[Point], precision: int = 2) -> Tuple[Tuple[float, float], ...]:
    ring = close_ring(points)
    if not ring:
        return tuple()
    body = [(round(x, precision), round(y, precision)) for x, y in ring[:-1]]
    if not body:
        return tuple()
    rotations = [tuple(body[index:] + body[:index]) for index in range(len(body))]
    reversed_body = list(reversed(body))
    rotations.extend(tuple(reversed_body[index:] + reversed_body[:index]) for index in range(len(reversed_body)))
    return min(rotations)


def orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a: Point, b: Point, c: Point, tolerance: float = 1e-9) -> bool:
    return (
        min(a[0], c[0]) - tolerance <= b[0] <= max(a[0], c[0]) + tolerance
        and min(a[1], c[1]) - tolerance <= b[1] <= max(a[1], c[1]) + tolerance
    )


def segments_intersect(a1: Point, a2: Point, b1: Point, b2: Point, tolerance: float = 1e-9) -> bool:
    o1 = orientation(a1, a2, b1)
    o2 = orientation(a1, a2, b2)
    o3 = orientation(b1, b2, a1)
    o4 = orientation(b1, b2, a2)

    if ((o1 > tolerance and o2 < -tolerance) or (o1 < -tolerance and o2 > tolerance)) and (
        (o3 > tolerance and o4 < -tolerance) or (o3 < -tolerance and o4 > tolerance)
    ):
        return True

    if abs(o1) <= tolerance and on_segment(a1, b1, a2, tolerance):
        return True
    if abs(o2) <= tolerance and on_segment(a1, b2, a2, tolerance):
        return True
    if abs(o3) <= tolerance and on_segment(b1, a1, b2, tolerance):
        return True
    if abs(o4) <= tolerance and on_segment(b1, a2, b2, tolerance):
        return True
    return False


def polygon_is_simple(points: Sequence[Point]) -> bool:
    ring = close_ring(points)
    if len(ring) < 4:
        return False
    segment_count = len(ring) - 1
    for i in range(segment_count):
        a1 = ring[i]
        a2 = ring[i + 1]
        for j in range(i + 1, segment_count):
            if abs(i - j) <= 1:
                continue
            if i == 0 and j == segment_count - 1:
                continue
            b1 = ring[j]
            b2 = ring[j + 1]
            if segments_intersect(a1, a2, b1, b2):
                return False
    return True


def approximate_arc(center: Point, radius: float, start_angle: float, end_angle: float, max_step_degrees: float = 15.0) -> List[Point]:
    start_radians = math.radians(start_angle)
    end_radians = math.radians(end_angle)
    sweep = end_radians - start_radians
    while sweep <= 0:
        sweep += 2 * math.pi
    step_count = max(2, int(math.ceil(abs(math.degrees(sweep)) / max_step_degrees)))
    points = []
    for step in range(step_count + 1):
        t = start_radians + sweep * step / step_count
        points.append((center[0] + radius * math.cos(t), center[1] + radius * math.sin(t)))
    return points


def approximate_circle(center: Point, radius: float, step_count: int = 48) -> List[Point]:
    points = []
    for step in range(step_count):
        angle = 2 * math.pi * step / step_count
        points.append((center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)))
    points.append(points[0])
    return points


def approximate_ellipse(entity: Entity, step_count: int = 64) -> List[Point]:
    if entity.center is None or entity.major_axis is None or entity.ratio is None:
        return []

    cx, cy = entity.center
    major_x, major_y = entity.major_axis
    ratio = entity.ratio
    minor_x = -major_y * ratio
    minor_y = major_x * ratio

    start_param = entity.start_param if entity.start_param is not None else 0.0
    end_param = entity.end_param if entity.end_param is not None else 2 * math.pi
    sweep = normalized_param_sweep(start_param, end_param)
    steps = max(8, int(math.ceil(step_count * sweep / (2 * math.pi))))

    points = []
    for step in range(steps + 1):
        t = start_param + sweep * step / steps
        cos_t = math.cos(t)
        sin_t = math.sin(t)
        x = cx + major_x * cos_t + minor_x * sin_t
        y = cy + major_y * cos_t + minor_y * sin_t
        points.append((x, y))
    return points


def _append_connected_path(ring: List[Point], path: Sequence[Point], tolerance: float = 1e-4) -> None:
    if not path:
        return
    if not ring:
        ring.extend(path)
        return
    if distance(ring[-1], path[0]) <= tolerance:
        ring.extend(path[1:])
    else:
        ring.extend(path)


def _edge_candidate_endpoints(candidates: Sequence[Sequence[Point]]) -> List[Point]:
    endpoints: List[Point] = []
    for candidate in candidates:
        if candidate:
            endpoints.append(candidate[0])
            endpoints.append(candidate[-1])
    return endpoints


def _choose_initial_hatch_edge(candidates_by_edge: Sequence[Sequence[List[Point]]]) -> List[Point]:
    first_candidates = candidates_by_edge[0]
    if len(candidates_by_edge) == 1:
        return first_candidates[0] if first_candidates else []

    previous_endpoints = _edge_candidate_endpoints(candidates_by_edge[-1])
    next_endpoints = _edge_candidate_endpoints(candidates_by_edge[1])

    def score(candidate: Sequence[Point]) -> float:
        if not candidate:
            return float("inf")
        previous_score = (
            min(distance(candidate[0], point) for point in previous_endpoints)
            if previous_endpoints
            else 0.0
        )
        next_score = (
            min(distance(candidate[-1], point) for point in next_endpoints)
            if next_endpoints
            else 0.0
        )
        return previous_score + next_score

    return min(first_candidates, key=score) if first_candidates else []


def _concatenate_hatch_edge_candidates(candidates_by_edge: Sequence[Sequence[List[Point]]]) -> List[Point]:
    if not candidates_by_edge or any(not candidates for candidates in candidates_by_edge):
        return []

    ring: List[Point] = []
    for index, candidates in enumerate(candidates_by_edge):
        if index == 0:
            chosen = _choose_initial_hatch_edge(candidates_by_edge)
        else:
            chosen = min(candidates, key=lambda candidate: distance(ring[-1], candidate[0]) if candidate else float("inf"))
        _append_connected_path(ring, chosen)

    return close_ring(ring)


def _parse_hatch_line_edge(tags: Sequence[Tuple[int, str]], index: int) -> Tuple[List[List[Point]], int]:
    x1 = y1 = x2 = y2 = None
    while index < len(tags) and None in (x1, y1, x2, y2):
        code, raw = tags[index]
        if code == 10:
            x1 = parse_float(raw)
        elif code == 20:
            y1 = parse_float(raw)
        elif code == 11:
            x2 = parse_float(raw)
        elif code == 21:
            y2 = parse_float(raw)
        index += 1
    if None in (x1, y1, x2, y2):
        return [], index
    path = [(x1, y1), (x2, y2)]
    return [path, list(reversed(path))], index


def _approximate_hatch_arc(
    center: Point,
    radius: float,
    start_angle: float,
    end_angle: float,
    ccw: bool,
    max_step_degrees: float = 15.0,
) -> List[Point]:
    start_radians = math.radians(start_angle)
    end_radians = math.radians(end_angle)
    sweep = end_radians - start_radians
    if ccw:
        while sweep <= 0:
            sweep += 2 * math.pi
    else:
        while sweep >= 0:
            sweep -= 2 * math.pi
    step_count = max(2, int(math.ceil(abs(math.degrees(sweep)) / max_step_degrees)))
    points = []
    for step in range(step_count + 1):
        t = start_radians + sweep * step / step_count
        points.append((center[0] + radius * math.cos(t), center[1] + radius * math.sin(t)))
    return points


def _parse_hatch_arc_edge(tags: Sequence[Tuple[int, str]], index: int) -> Tuple[List[List[Point]], int]:
    cx = cy = radius = start_angle = end_angle = ccw = None
    while index < len(tags) and None in (cx, cy, radius, start_angle, end_angle, ccw):
        code, raw = tags[index]
        if code == 10:
            cx = parse_float(raw)
        elif code == 20:
            cy = parse_float(raw)
        elif code == 40:
            radius = parse_float(raw)
        elif code == 50:
            start_angle = parse_float(raw)
        elif code == 51:
            end_angle = parse_float(raw)
        elif code == 73:
            ccw = parse_int(raw)
        index += 1
    if None in (cx, cy, radius, start_angle, end_angle, ccw):
        return [], index
    center = (cx, cy)
    candidates: List[List[Point]] = []
    for angle_sign in (1.0, -1.0):
        path = _approximate_hatch_arc(
            center,
            radius,
            angle_sign * start_angle,
            angle_sign * end_angle,
            ccw=bool(ccw),
        )
        if path:
            candidates.append(path)
            candidates.append(list(reversed(path)))
    return candidates, index


def _hatch_ellipse_candidate(
    center: Point,
    major_axis: Point,
    ratio: float,
    start_angle: float,
    end_angle: float,
) -> List[Point]:
    entity = Entity(
        entity_id="_hatch_ellipse",
        type="ELLIPSE",
        layer="",
        family=None,
        center=center,
        major_axis=major_axis,
        ratio=ratio,
        start_param=math.radians(start_angle),
        end_param=math.radians(end_angle),
    )
    return approximate_ellipse(entity)


def _parse_hatch_ellipse_edge(tags: Sequence[Tuple[int, str]], index: int) -> Tuple[List[List[Point]], int]:
    cx = cy = major_x = major_y = ratio = start_angle = end_angle = ccw = None
    while index < len(tags) and None in (cx, cy, major_x, major_y, ratio, start_angle, end_angle, ccw):
        code, raw = tags[index]
        if code == 10:
            cx = parse_float(raw)
        elif code == 20:
            cy = parse_float(raw)
        elif code == 11:
            major_x = parse_float(raw)
        elif code == 21:
            major_y = parse_float(raw)
        elif code == 40:
            ratio = parse_float(raw)
        elif code == 50:
            start_angle = parse_float(raw)
        elif code == 51:
            end_angle = parse_float(raw)
        elif code == 73:
            ccw = parse_int(raw)
        index += 1
    if None in (cx, cy, major_x, major_y, ratio, start_angle, end_angle, ccw):
        return [], index
    if ccw == 0:
        start_angle, end_angle = end_angle, start_angle

    center = (cx, cy)
    candidates: List[List[Point]] = []
    for major_axis in ((major_x, major_y), (-major_x, -major_y)):
        path = _hatch_ellipse_candidate(center, major_axis, ratio, start_angle, end_angle)
        if path:
            candidates.append(path)
            candidates.append(list(reversed(path)))
    return candidates, index


def _parse_hatch_polyline_path(tags: Sequence[Tuple[int, str]], index: int) -> Tuple[List[Point], int]:
    path_tags: List[Tuple[int, str]] = []
    vertex_count: Optional[int] = None
    while index < len(tags):
        code, raw = tags[index]
        path_tags.append((code, raw))
        index += 1
        if code == 93:
            vertex_count = parse_int(raw)
            break
        if code == 92:
            return [], index - 1

    if vertex_count is None:
        return [], index

    vertices_seen = 0
    awaiting_y = False
    while index < len(tags) and vertices_seen < vertex_count:
        code, raw = tags[index]
        path_tags.append((code, raw))
        index += 1
        if code == 10:
            awaiting_y = True
        elif code == 20 and awaiting_y:
            vertices_seen += 1
            awaiting_y = False

    while index < len(tags) and tags[index][0] == 42:
        path_tags.append(tags[index])
        index += 1

    points = parse_lwpolyline_points(path_tags)
    return close_ring(flatten_polyline_points(points, closed=True)), index


def _parse_hatch_edge_path(tags: Sequence[Tuple[int, str]], index: int) -> Tuple[List[Point], int]:
    edge_count: Optional[int] = None
    while index < len(tags):
        code, raw = tags[index]
        index += 1
        if code == 93:
            edge_count = parse_int(raw)
            break
        if code == 92:
            return [], index - 1

    if edge_count is None:
        return [], index

    candidates_by_edge: List[List[List[Point]]] = []
    for _ in range(edge_count):
        while index < len(tags) and tags[index][0] != 72:
            if tags[index][0] in {92, 75, 76, 98, 450}:
                return _concatenate_hatch_edge_candidates(candidates_by_edge), index
            index += 1
        if index >= len(tags):
            break

        edge_type = parse_int(tags[index][1])
        index += 1
        if edge_type == 1:
            candidates, index = _parse_hatch_line_edge(tags, index)
        elif edge_type == 2:
            candidates, index = _parse_hatch_arc_edge(tags, index)
        elif edge_type == 3:
            candidates, index = _parse_hatch_ellipse_edge(tags, index)
        else:
            candidates = []
        candidates_by_edge.append(candidates)

    return _concatenate_hatch_edge_candidates(candidates_by_edge), index


def parse_hatch_boundary_paths(tags: Sequence[Tuple[int, str]]) -> List[HatchBoundaryPath]:
    boundary_count: Optional[int] = None
    index = 0
    for tag_index, (code, raw) in enumerate(tags):
        if code == 91:
            boundary_count = parse_int(raw)
            index = tag_index + 1
            break
    if boundary_count is None:
        return []

    paths: List[HatchBoundaryPath] = []
    while index < len(tags) and len(paths) < boundary_count:
        code, raw = tags[index]
        if code != 92:
            index += 1
            continue

        flags = parse_int(raw)
        index += 1
        if flags & HATCH_PATH_POLYLINE:
            points, index = _parse_hatch_polyline_path(tags, index)
        else:
            points, index = _parse_hatch_edge_path(tags, index)
        if points:
            paths.append(HatchBoundaryPath(flags=flags, points=points))

    return paths


def flatten_polyline_points(points: Sequence[Tuple[float, float, float]], closed: bool) -> List[Point]:
    flat = [(x, y) for x, y, _ in points]
    if closed and flat and distance(flat[0], flat[-1]) > 1e-6:
        flat.append(flat[0])
    return flat


def entity_to_draw_paths(entity: Entity) -> List[List[Point]]:
    if entity.type == "LINE" and entity.start and entity.end:
        return [[entity.start, entity.end]]
    if entity.type == "ARC" and entity.center and entity.radius is not None and entity.start_angle is not None and entity.end_angle is not None:
        return [approximate_arc(entity.center, entity.radius, entity.start_angle, entity.end_angle)]
    if entity.type == "CIRCLE" and entity.center and entity.radius is not None:
        return [approximate_circle(entity.center, entity.radius)]
    if entity.type == "ELLIPSE":
        points = approximate_ellipse(entity)
        return [points] if points else []
    if entity.type in {"LWPOLYLINE", "POLYLINE"} and entity.points:
        return [flatten_polyline_points(entity.points, entity.closed)]
    if entity.type == "HATCH" and entity.hatch_paths:
        if entity.family is None:
            return [path.points for path in entity.hatch_paths if path.points]
        return [
            path.points
            for path in entity.hatch_paths
            if path.is_outer_candidate and family_accepts_polygon(entity.family, path.points)
        ]
    return []


def family_accepts_polygon(family: str, ring: Sequence[Point]) -> bool:
    ring = close_ring(ring)
    if len(ring) < 4:
        return False
    area = abs(polygon_area(ring))
    bbox = polygon_bbox(ring)
    aspect = aspect_ratio_from_bbox(bbox)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    major = max(width, height)
    minor = min(width, height)

    if family == "walls":
        return area >= 20.0 and major >= 4.0 and (aspect >= 1.2 or area >= 500.0)
    if family == "columns":
        return 10.0 <= area <= 20000.0 and major <= 500.0 and aspect <= 8.0 and minor >= 1.0
    if family == "curtain_walls":
        return area >= 2.0 and major >= 1.0 and aspect >= 1.05
    return False


def polygon_record(
    family: str,
    ring: Sequence[Point],
    source_layers: Iterable[str],
    source_entity_ids: Iterable[str],
    source_kind: str,
) -> Optional[PolygonRecord]:
    closed = ensure_clockwise(ring)
    if not closed or len(closed) < 4:
        return None
    if not polygon_is_simple(closed):
        return None
    if not family_accepts_polygon(family, closed):
        return None
    area = abs(polygon_area(closed))
    bbox = polygon_bbox(closed)
    return PolygonRecord(
        family=family,
        vertices=closed,
        source_layers=sorted(set(source_layers)),
        source_entity_ids=sorted(set(source_entity_ids)),
        source_kind=source_kind,
        area=area,
        bbox=bbox,
        aspect_ratio=aspect_ratio_from_bbox(bbox),
    )


def extract_direct_polygons(entities: Sequence[Entity]) -> List[PolygonRecord]:
    polygons: List[PolygonRecord] = []
    for entity in entities:
        if entity.family is None:
            continue
        ring: List[Point] = []
        if entity.type == "CIRCLE" and entity.center and entity.radius is not None:
            ring = approximate_circle(entity.center, entity.radius)
        elif entity.type == "ELLIPSE" and entity.closed:
            ring = approximate_ellipse(entity)
            ring = close_ring(ring)
        elif entity.type in {"LWPOLYLINE", "POLYLINE"} and entity.points and entity.closed:
            ring = close_ring(flatten_polyline_points(entity.points, closed=True))
        else:
            continue
        record = polygon_record(
            family=entity.family,
            ring=ring,
            source_layers=[entity.layer],
            source_entity_ids=[entity.entity_id],
            source_kind=f"direct_{entity.type.lower()}",
        )
        if record is not None:
            polygons.append(record)
    return polygons


def extract_hatch_polygons(entities: Sequence[Entity]) -> List[PolygonRecord]:
    polygons: List[PolygonRecord] = []
    for entity in entities:
        if entity.family is None or entity.type != "HATCH":
            continue
        for path in entity.hatch_paths:
            if not path.is_outer_candidate:
                continue
            record = polygon_record(
                family=entity.family,
                ring=path.points,
                source_layers=[entity.layer],
                source_entity_ids=[entity.entity_id],
                source_kind="direct_hatch",
            )
            if record is not None:
                polygons.append(record)
    return polygons


def entity_to_segments(entity: Entity) -> List[Segment]:
    if entity.family is None:
        return []
    if entity.type == "HATCH":
        return []
    if entity.type in {"CIRCLE"}:
        return []
    if entity.type in {"LWPOLYLINE", "POLYLINE"} and entity.closed:
        return []

    paths = entity_to_draw_paths(entity)
    segments: List[Segment] = []
    for path in paths:
        for index in range(len(path) - 1):
            start = path[index]
            end = path[index + 1]
            if distance(start, end) <= 1e-6:
                continue
            segments.append(
                Segment(
                    family=entity.family,
                    layer=entity.layer,
                    entity_id=entity.entity_id,
                    start=start,
                    end=end,
                )
            )
    return segments


def snap_point(point: Point, tolerance: float) -> Point:
    return (round(point[0] / tolerance) * tolerance, round(point[1] / tolerance) * tolerance)


SnapTolerance = Union[float, Mapping[str, float]]


def _tolerance_for_family(tolerance: SnapTolerance, family: str) -> float:
    if isinstance(tolerance, (int, float)):
        return float(tolerance)
    if family in tolerance:
        return float(tolerance[family])
    if "__default__" in tolerance:
        return float(tolerance["__default__"])
    # Fall back to the mean of provided families; keeps per-family maps
    # that only list one or two families behaving sensibly.
    values = list(tolerance.values())
    return sum(values) / len(values) if values else 0.5


def extract_faces_from_segments(segments: Sequence[Segment], tolerance: SnapTolerance) -> List[PolygonRecord]:
    by_family: Dict[str, List[Segment]] = defaultdict(list)
    for segment in segments:
        by_family[segment.family].append(segment)

    polygons: List[PolygonRecord] = []

    for family, family_segments in by_family.items():
        family_tolerance = _tolerance_for_family(tolerance, family)
        merged: Dict[Tuple[Point, Point], Dict[str, object]] = {}
        for segment in family_segments:
            a = snap_point(segment.start, family_tolerance)
            b = snap_point(segment.end, family_tolerance)
            if distance(a, b) <= 1e-9:
                continue
            key = (a, b) if a <= b else (b, a)
            payload = merged.setdefault(
                key,
                {
                    "a": a,
                    "b": b,
                    "layers": set(),
                    "entity_ids": set(),
                },
            )
            payload["layers"].add(segment.layer)
            payload["entity_ids"].add(segment.entity_id)

        outgoing: Dict[Point, List[int]] = defaultdict(list)
        half_edges: List[Dict[str, object]] = []

        for edge_index, payload in enumerate(merged.values()):
            a = payload["a"]
            b = payload["b"]
            angle_ab = math.atan2(b[1] - a[1], b[0] - a[0])
            angle_ba = math.atan2(a[1] - b[1], a[0] - b[0])
            forward_id = len(half_edges)
            backward_id = forward_id + 1
            half_edges.append(
                {
                    "origin": a,
                    "dest": b,
                    "angle": angle_ab,
                    "twin": backward_id,
                    "edge_index": edge_index,
                    "layers": payload["layers"],
                    "entity_ids": payload["entity_ids"],
                }
            )
            half_edges.append(
                {
                    "origin": b,
                    "dest": a,
                    "angle": angle_ba,
                    "twin": forward_id,
                    "edge_index": edge_index,
                    "layers": payload["layers"],
                    "entity_ids": payload["entity_ids"],
                }
            )
            outgoing[a].append(forward_id)
            outgoing[b].append(backward_id)

        position_lookup: Dict[int, int] = {}
        for node, half_edge_ids in outgoing.items():
            half_edge_ids.sort(key=lambda edge_id: half_edges[edge_id]["angle"])
            for position, edge_id in enumerate(half_edge_ids):
                position_lookup[edge_id] = position

        visited: set[int] = set()
        family_seen: set[Tuple[Tuple[float, float], ...]] = set()

        for start_half_edge in range(len(half_edges)):
            if start_half_edge in visited:
                continue
            cycle: List[int] = []
            cursor = start_half_edge
            guard = 0
            while cursor not in cycle:
                cycle.append(cursor)
                guard += 1
                if guard > len(half_edges) + 4:
                    cycle = []
                    break
                twin_id = half_edges[cursor]["twin"]
                node = half_edges[cursor]["dest"]
                candidates = outgoing[node]
                if not candidates:
                    cycle = []
                    break
                twin_position = position_lookup[twin_id]
                cursor = candidates[(twin_position - 1) % len(candidates)]
            if not cycle:
                continue
            if cursor != start_half_edge:
                continue

            for edge_id in cycle:
                visited.add(edge_id)

            ring = [half_edges[edge_id]["origin"] for edge_id in cycle]
            ring.append(ring[0])
            signed_area = polygon_area(ring)
            if signed_area <= 1e-6:
                continue
            signature = rotate_canonical(ring, precision=2)
            if signature in family_seen:
                continue
            family_seen.add(signature)

            layers = set()
            entity_ids = set()
            for edge_id in cycle:
                layers.update(half_edges[edge_id]["layers"])
                entity_ids.update(half_edges[edge_id]["entity_ids"])

            record = polygon_record(
                family=family,
                ring=ring,
                source_layers=layers,
                source_entity_ids=entity_ids,
                source_kind="graph_face",
            )
            if record is not None:
                polygons.append(record)

    return polygons


def dedupe_polygons(polygons: Sequence[PolygonRecord]) -> List[PolygonRecord]:
    merged: Dict[Tuple[str, float, float, float, float, float, float], PolygonRecord] = {}
    for polygon in polygons:
        min_x, min_y, max_x, max_y = polygon.bbox
        # Location is part of the key through the rounded bbox, so this only
        # merges duplicate recoveries of the same local shape, not repeated
        # identical columns or panels elsewhere in the plan.
        key = (
            polygon.family,
            round(polygon.area, 1),
            round(min_x, 1),
            round(min_y, 1),
            round(max_x, 1),
            round(max_y, 1),
            round(polygon.aspect_ratio, 2),
        )
        existing = merged.get(key)
        if existing is None:
            merged[key] = polygon
            continue
        existing_layers = set(existing.source_layers)
        existing_entities = set(existing.source_entity_ids)
        existing_layers.update(polygon.source_layers)
        existing_entities.update(polygon.source_entity_ids)
        existing.source_layers = sorted(existing_layers)
        existing.source_entity_ids = sorted(existing_entities)
        if polygon.source_kind.startswith("direct"):
            existing.source_kind = polygon.source_kind
    return sorted(merged.values(), key=lambda record: (record.family, record.bbox[1], record.bbox[0], record.area))


def entity_length(entity: Entity) -> float:
    if entity.type == "LINE" and entity.start and entity.end:
        return distance(entity.start, entity.end)
    if entity.type == "ARC" and entity.radius is not None and entity.start_angle is not None and entity.end_angle is not None:
        sweep = entity.end_angle - entity.start_angle
        while sweep <= 0:
            sweep += 360.0
        return entity.radius * math.radians(sweep)
    if entity.type == "CIRCLE" and entity.radius is not None:
        return 2 * math.pi * entity.radius
    if entity.type == "ELLIPSE" and entity.major_axis and entity.ratio is not None:
        a = math.hypot(entity.major_axis[0], entity.major_axis[1])
        b = a * entity.ratio
        start_param = entity.start_param if entity.start_param is not None else 0.0
        end_param = entity.end_param if entity.end_param is not None else 2 * math.pi
        sweep = normalized_param_sweep(start_param, end_param)
        circumference = math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))
        return circumference * (sweep / (2 * math.pi))
    if entity.type in {"LWPOLYLINE", "POLYLINE"} and entity.points:
        flat = flatten_polyline_points(entity.points, entity.closed)
        return sum(distance(flat[index], flat[index + 1]) for index in range(len(flat) - 1))
    if entity.type == "HATCH" and entity.hatch_paths:
        return sum(
            distance(path[index], path[index + 1])
            for path in entity_to_draw_paths(entity)
            for index in range(len(path) - 1)
        )
    return 0.0


def generate_polygon_id(polygon: PolygonRecord, index: int) -> str:
    """Generate AIA-grammar-aware polygon ID from source layers."""
    source = polygon.source_layers
    if len(source) == 1:
        prefix = LAYER_ID_PREFIX.get(source[0])
        if prefix:
            return f"{prefix}_{index:04d}"
    elif len(source) > 1:
        # Multi-layer: find most specific prefix, tag as multi
        for layer in source:
            prefix = LAYER_ID_PREFIX.get(layer)
            if prefix:
                return f"{prefix}_multi_{index:04d}"
    # Fallback for unknown layers outside the scoped family map.
    fallback = FAMILY_ID_FALLBACK.get(polygon.family, "unk")
    return f"{fallback}_{index:04d}"


def polygon_to_json(polygon_id: str, polygon: PolygonRecord) -> Dict[str, object]:
    return {
        "id": polygon_id,
        "source_layers": polygon.source_layers,
        "vertices": [
            {"x_coord": round(x, 6), "y_coord": round(y, 6)}
            for x, y in polygon.vertices[:-1]
        ],
    }


def compute_snap_stats(entities: Sequence[Entity], wall_tolerances: Sequence[float]) -> Dict[str, Dict[str, int]]:
    wall_entities = [
        entity
        for entity in entities
        if entity.family == "walls" and entity.type in {"LINE", "ARC", "LWPOLYLINE", "POLYLINE"}
    ]
    stats: Dict[str, Dict[str, int]] = {}
    for tolerance in wall_tolerances:
        degree_counter: Counter[Point] = Counter()
        for entity in wall_entities:
            for segment in entity_to_segments(entity):
                degree_counter[snap_point(segment.start, tolerance)] += 1
                degree_counter[snap_point(segment.end, tolerance)] += 1
        histogram = Counter(degree_counter.values())
        stats[str(tolerance)] = {
            "nodes": sum(histogram.values()),
            "degree_1": histogram.get(1, 0),
            "degree_2": histogram.get(2, 0),
            "degree_3": histogram.get(3, 0),
            "degree_4_plus": sum(count for degree, count in histogram.items() if degree >= 4),
        }
    return stats


ADAPTIVE_CANDIDATE_TOLERANCES: Tuple[float, ...] = (0.1, 0.25, 0.5, 1.0)


def pick_best_wall_tolerance(
    entities: Sequence[Entity],
    candidates: Sequence[float] = ADAPTIVE_CANDIDATE_TOLERANCES,
    fallback: float = 0.5,
) -> float:
    """Choose one tolerance from a small wall-connectivity sweep.

    This scores the documented candidates by the local change in the wall
    degree-4+ curve and returns the strongest interior candidate. The
    documented default run remains 0.5.
    """
    stats = compute_snap_stats(entities, wall_tolerances=candidates)
    tols = sorted(candidates)
    deg4 = [stats[str(t)]["degree_4_plus"] for t in tols]
    if len(tols) < 3:
        return tols[len(tols) // 2]
    first = [deg4[i + 1] - deg4[i] for i in range(len(deg4) - 1)]
    second = [first[i + 1] - first[i] for i in range(len(first) - 1)]
    if not second:
        return fallback
    best = max(range(len(second)), key=lambda i: second[i])
    return tols[best + 1]


def resolve_snap_tolerance(arg: str, entities: Optional[Sequence[Entity]] = None) -> SnapTolerance:
    """Parse a ``--snap-tolerance`` CLI argument into a tolerance value.

    Accepted forms:

    - ``"0.5"``                        uniform scalar
    - ``"walls=0.5,columns=0.25"``     per-family, missing families fall back
                                       to the mean of provided values
    - ``"adaptive"``                   best scalar from the small wall
                                       connectivity sweep
                                       (requires ``entities`` to be provided)
    """
    text = arg.strip()
    if text == "adaptive":
        if entities is None:
            raise ValueError("adaptive snap tolerance requires parsed entities")
        return pick_best_wall_tolerance(entities)
    if "=" in text:
        parsed: Dict[str, float] = {}
        for token in text.split(","):
            key, _, value = token.strip().partition("=")
            key = key.strip()
            value = value.strip()
            if not key or not value:
                raise ValueError(f"malformed --snap-tolerance entry: {token!r}")
            parsed[key] = float(value)
        if not parsed:
            raise ValueError(f"empty per-family snap map: {text!r}")
        return parsed
    return float(text)


def snap_tolerance_for_report(tolerance: SnapTolerance) -> float:
    """Single scalar for report filenames and legacy fields."""
    if isinstance(tolerance, (int, float)):
        return float(tolerance)
    return _tolerance_for_family(tolerance, "walls")


def entity_extent(entity: Entity) -> Optional[Tuple[float, float, float, float]]:
    paths = entity_to_draw_paths(entity)
    points = [point for path in paths for point in path]
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def combine_extents(extents: Sequence[Tuple[float, float, float, float]]) -> Optional[Tuple[float, float, float, float]]:
    if not extents:
        return None
    min_x = min(extent[0] for extent in extents)
    min_y = min(extent[1] for extent in extents)
    max_x = max(extent[2] for extent in extents)
    max_y = max(extent[3] for extent in extents)
    return min_x, min_y, max_x, max_y


def svg_transform(extent: Tuple[float, float, float, float], width: int = 1800, padding: int = 24):
    min_x, min_y, max_x, max_y = extent
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    scale = (width - 2 * padding) / span_x
    height = int(math.ceil(span_y * scale + 2 * padding))

    def project(point: Point) -> Point:
        x = padding + (point[0] - min_x) * scale
        y = padding + (max_y - point[1]) * scale
        return x, y

    return project, width, height


def write_svg(
    path: Path,
    extent: Tuple[float, float, float, float],
    entities: Sequence[Entity],
    polygons: Sequence[PolygonRecord],
    entity_filter=None,
    polygon_filter=None,
) -> None:
    project, width, height = svg_transform(extent)
    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>',
    ]

    for entity in entities:
        if entity_filter and not entity_filter(entity):
            continue
        color = "#b8b8b8"
        opacity = "0.55"
        stroke_width = "1"
        if entity.family in FAMILY_COLORS:
            color = FAMILY_COLORS[entity.family]
            opacity = "0.35"
        for path_points in entity_to_draw_paths(entity):
            if len(path_points) < 2:
                continue
            projected = [project(point) for point in path_points]
            path_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in projected)
            lines.append(
                f'<polyline fill="none" stroke="{color}" stroke-opacity="{opacity}" stroke-width="{stroke_width}" points="{path_text}"/>'
            )

    for polygon in polygons:
        if polygon_filter and not polygon_filter(polygon):
            continue
        color = FAMILY_COLORS[polygon.family]
        projected = [project(point) for point in polygon.vertices]
        point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in projected)
        lines.append(
            f'<polygon fill="{color}" fill-opacity="0.16" stroke="{color}" stroke-width="1.25" points="{point_text}"/>'
        )

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_wall_connectivity_svg(path: Path, segments: Sequence[Segment], tolerance: float) -> None:
    wall_segments = [segment for segment in segments if segment.family == "walls"]
    if not wall_segments:
        return
    extents = [
        (
            min(segment.start[0], segment.end[0]),
            min(segment.start[1], segment.end[1]),
            max(segment.start[0], segment.end[0]),
            max(segment.start[1], segment.end[1]),
        )
        for segment in wall_segments
    ]
    extent = combine_extents(extents)
    if extent is None:
        return
    project, width, height = svg_transform(extent)
    degree_counter: Counter[Point] = Counter()
    snapped_segments = []
    for segment in wall_segments:
        start = snap_point(segment.start, tolerance)
        end = snap_point(segment.end, tolerance)
        degree_counter[start] += 1
        degree_counter[end] += 1
        snapped_segments.append((start, end))

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>',
    ]
    for start, end in snapped_segments:
        x1, y1 = project(start)
        x2, y2 = project(end)
        lines.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#999999" stroke-opacity="0.45" stroke-width="0.8"/>'
        )
    for point, degree in degree_counter.items():
        x, y = project(point)
        radius = 1.2 if degree <= 2 else 1.8 if degree == 3 else 2.6
        color = "#888888" if degree <= 2 else "#f39c12" if degree == 3 else "#d9342b"
        lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{color}" fill-opacity="0.9"/>')
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def family_polygon_counts(polygons: Sequence[PolygonRecord]) -> Dict[str, int]:
    counts = Counter(polygon.family for polygon in polygons)
    return {family: counts.get(family, 0) for family in ["walls", "columns", "curtain_walls"]}


def hatch_extraction_stats(entities: Sequence[Entity], polygons: Sequence[PolygonRecord]) -> Dict[str, int]:
    hatch_entities = [entity for entity in entities if entity.family and entity.type == "HATCH"]
    hatch_paths = [path for entity in hatch_entities for path in entity.hatch_paths]
    return {
        "entities": len(hatch_entities),
        "parsed_paths": len(hatch_paths),
        "outer_candidate_paths": sum(1 for path in hatch_paths if path.is_outer_candidate),
        "skipped_hole_or_default_paths": sum(1 for path in hatch_paths if not path.is_outer_candidate),
        "direct_hatch_polygons": sum(1 for polygon in polygons if polygon.source_kind == "direct_hatch"),
    }


def build_analysis_summary(
    entities: Sequence[Entity],
    polygons: Sequence[PolygonRecord],
    runtime_seconds: float,
    snap_stats: Dict[str, Dict[str, int]],
) -> Dict[str, object]:
    type_counts = Counter(entity.type for entity in entities)
    layer_counts = Counter(entity.layer for entity in entities)
    family_entity_counts = Counter(entity.family for entity in entities if entity.family)
    target_entities = [entity for entity in entities if entity.family]

    layer_type_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for entity in target_entities:
        layer_type_counts[entity.layer][entity.type] += 1

    total_target_length = sum(entity_length(entity) for entity in target_entities)
    consumed_entity_ids = {entity_id for polygon in polygons for entity_id in polygon.source_entity_ids}
    consumed_target_entities = [entity for entity in target_entities if entity.entity_id in consumed_entity_ids]
    consumed_target_length = sum(entity_length(entity) for entity in consumed_target_entities)

    return {
        "runtime_seconds": runtime_seconds,
        "entity_type_counts": dict(type_counts.most_common()),
        "top_layers": dict(layer_counts.most_common(25)),
        "family_entity_counts": dict(family_entity_counts),
        "target_layer_type_counts": {layer: dict(sorted(type_counts.items())) for layer, type_counts in sorted(layer_type_counts.items())},
        "polygon_counts": family_polygon_counts(polygons),
        "graph_vs_direct_counts": {
            "direct": sum(1 for polygon in polygons if polygon.source_kind.startswith("direct")),
            "graph_face": sum(1 for polygon in polygons if polygon.source_kind == "graph_face"),
        },
        "source_kind_counts": dict(Counter(polygon.source_kind for polygon in polygons).most_common()),
        "hatch_extraction": hatch_extraction_stats(entities, polygons),
        "target_primitive_totals": {
            "count": len(target_entities),
            "length_total": round(total_target_length, 3),
            "count_consumed": len(consumed_target_entities),
            "length_consumed": round(consumed_target_length, 3),
            "length_coverage_estimate": round(consumed_target_length / total_target_length, 4) if total_target_length else 0.0,
            "coverage_method": "source_entity_length_proxy",
            "coverage_note": (
                "Proxy metric: sums drawable length of scoped source entities "
                "referenced by accepted polygons. It is not the brief's exact "
                "inside-or-near-output-polygon coverage calculation."
            ),
        },
        "wall_snap_stats": snap_stats,
    }


def build_output_json(
    polygons: Sequence[PolygonRecord],
    entities: Sequence[Entity],
    runtime_seconds: float,
) -> Dict[str, object]:
    grouped: Dict[str, List[PolygonRecord]] = defaultdict(list)
    for polygon in polygons:
        grouped[polygon.family].append(polygon)

    target_entities = [entity for entity in entities if entity.family]
    consumed_entity_ids = {entity_id for polygon in polygons for entity_id in polygon.source_entity_ids}

    return {
        "walls": [polygon_to_json(generate_polygon_id(p, i + 1), p) for i, p in enumerate(grouped["walls"])],
        "columns": [polygon_to_json(generate_polygon_id(p, i + 1), p) for i, p in enumerate(grouped["columns"])],
        "curtain_walls": [polygon_to_json(generate_polygon_id(p, i + 1), p) for i, p in enumerate(grouped["curtain_walls"])],
        "metrics": {
            "runtime_seconds": round(runtime_seconds, 3),
            "primitives_consumed": len(consumed_entity_ids),
            "primitives_total": len(target_entities),
            "warnings": [
                f"Missing scoped layers: {', '.join(sorted(missing_layers(entities)))}"
                if missing_layers(entities)
                else "All scoped layers present."
            ],
        },
    }


def missing_layers(entities: Sequence[Entity]) -> List[str]:
    present_layers = {entity.layer for entity in entities}
    scoped = {layer for layers in FAMILY_LAYER_MAP.values() for layer in layers}
    return sorted(layer for layer in scoped if layer not in present_layers)


def write_analysis_report(path: Path, summary: Dict[str, object]) -> None:
    polygon_counts = summary["polygon_counts"]
    target_totals = summary["target_primitive_totals"]
    wall_snap_stats = summary["wall_snap_stats"]
    hatch_stats = summary["hatch_extraction"]
    lines = [
        "# DXF Analysis Report",
        "",
        "## Raw File Organization",
        "",
        f"- Runtime for parse + extraction: `{summary['runtime_seconds']:.2f}s`",
        f"- Primitive types are dominated by `LINE` with `{summary['entity_type_counts'].get('LINE', 0)}` entities, followed by `LWPOLYLINE`, `ELLIPSE`, `HATCH`, and `ARC`.",
        f"- Scoped target primitives total `{target_totals['count']}` entities with an estimated drawable length of `{target_totals['length_total']}` units.",
        f"- Source-entity coverage proxy is `{target_totals['length_consumed']}` units, or `{target_totals['length_coverage_estimate']:.1%}` of scoped drawable length.",
        "- Coverage caveat: this is a source-entity-length proxy, not the grader's exact primitive-length-inside-output-polygons metric.",
        "",
        "## Target Family Counts",
        "",
        f"- Walls extracted: `{polygon_counts['walls']}`",
        f"- Columns extracted: `{polygon_counts['columns']}`",
        f"- Curtain walls extracted: `{polygon_counts['curtain_walls']}`",
        f"- Direct HATCH polygons extracted: `{hatch_stats['direct_hatch_polygons']}` from `{hatch_stats['outer_candidate_paths']}` outer/external HATCH paths; `{hatch_stats['skipped_hole_or_default_paths']}` non-outer paths skipped as hole/default candidates.",
        "",
        "## Connectivity Callouts",
        "",
    ]
    for tolerance, stats in wall_snap_stats.items():
        lines.append(
            f"- Snap `{tolerance}`: `{stats['nodes']}` nodes, `{stats['degree_1']}` leaves, `{stats['degree_2']}` degree-2 nodes, `{stats['degree_3']}` degree-3 nodes, `{stats['degree_4_plus']}` degree-4+ junctions."
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The data behaves like a tokenization problem: direct closed carriers give obvious tokens, while wall linework requires graph-based closure recovery.",
            "- Columns combine strong direct carriers (circles, compact polylines) with companion-layer HATCH boundaries where those paths qualify as outer loops.",
            "- Walls remain the hardest family because they are dominated by open linework, mixed drafting conventions, and high-degree junctions after snapping.",
            "- Curtain wall layers are structurally regular and would benefit from a second-pass grid detector if coverage mattered more than turnaround time.",
            "",
            "## Representation Lens",
            "",
            "- Treat raw primitives as composable low-level geometry and closed polygons as tokens that satisfy closure and orientation laws.",
            "- Endpoint snapping collapses nearby coordinates before composition is valid.",
            "- Family typing maps geometry into architectural vocabulary while preserving source-layer provenance.",
            "",
            "## Learning Extension",
            "",
            "- The geometric pipeline owns deterministic structure: closure, winding, validity, and layer priors.",
            "- Learned tolerance, family disambiguation, and correction-on-feedback belong above that layer.",
            "- A future GNN would not replace geometry; it would propagate uncertainty and drafting-style context over the object graph produced here.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def load_normalization(norm_path: Optional[Path]) -> Optional[Dict]:
    """Load normalization.json if provided. Overrides hardcoded maps when present."""
    if norm_path is None or not norm_path.exists():
        return None
    with norm_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def apply_normalization(norm: Dict) -> None:
    """Override module-level maps from normalization output, making it the source of truth."""
    global LAYER_ID_PREFIX
    if "id_prefix_map" in norm:
        LAYER_ID_PREFIX = norm["id_prefix_map"]

    if "layer_map" in norm:
        # Update FAMILY_LAYER_MAP to include healed layer names
        layer_map = norm["layer_map"]
        for family, layers in FAMILY_LAYER_MAP.items():
            healed = set()
            for layer in layers:
                healed.add(layer_map.get(layer, layer))
            layers.update(healed)
        # Rebuild canonical map
        for family, layers in FAMILY_LAYER_MAP.items():
            CANONICAL_FAMILY_LAYERS[family] = {
                re.sub(r"[-\s]+", " ", layer.upper()).strip() for layer in layers
            }


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a DXF floor plan into architectural polygons and exploratory artifacts.")
    parser.add_argument("input_dxf", type=Path, help="Path to the source DXF file.")
    parser.add_argument("output_dir", type=Path, help="Directory for JSON, SVG, and report outputs.")
    parser.add_argument(
        "--mode",
        choices=sorted(SNAP_TOLERANCE_MODES),
        default="conservative",
        help=(
            "Named extraction preset. conservative=0.5 (submission/audit "
            "default, matches checked-in out/), liberal=0.75 (slightly "
            "wider snap, recovers a few more candidates with mild "
            "over-merging). --snap-tolerance overrides --mode when given."
        ),
    )
    parser.add_argument(
        "--snap-tolerance",
        type=str,
        default=None,
        help=(
            "Advanced override: scalar (e.g. '0.5'), per-family map "
            "('walls=0.5,columns=0.25,curtain_walls=0.35'), or "
            "'adaptive' (small wall-connectivity preset sweep). "
            "Overrides --mode when provided."
        ),
    )
    parser.add_argument("--normalization", type=Path, default=None, help="Path to normalization.json (overrides hardcoded maps).")
    args = parser.parse_args()
    effective_snap_tolerance = args.snap_tolerance if args.snap_tolerance is not None else SNAP_TOLERANCE_MODES[args.mode]

    # Load normalization output if provided — makes it the source of truth for maps
    norm = load_normalization(args.normalization)
    if norm is not None:
        apply_normalization(norm)

    start_time = time.time()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    entities = list(iter_entities(args.input_dxf))

    missing = missing_layers(entities)
    if missing:
        import sys
        for layer in missing:
            print(f"WARNING: scoped layer not found in file: {layer}", file=sys.stderr)

    if args.snap_tolerance is not None:
        snap_tolerance = resolve_snap_tolerance(args.snap_tolerance, entities=entities)
    else:
        snap_tolerance = SNAP_TOLERANCE_MODES[args.mode]
    report_tolerance = snap_tolerance_for_report(snap_tolerance)

    direct_polygons = extract_direct_polygons(entities)
    hatch_polygons = extract_hatch_polygons(entities)
    graph_segments = [segment for entity in entities for segment in entity_to_segments(entity)]
    graph_polygons = extract_faces_from_segments(graph_segments, tolerance=snap_tolerance)
    polygons = dedupe_polygons(direct_polygons + hatch_polygons + graph_polygons)
    runtime_seconds = time.time() - start_time

    summary = build_analysis_summary(
        entities=entities,
        polygons=polygons,
        runtime_seconds=runtime_seconds,
        snap_stats=compute_snap_stats(entities, wall_tolerances=[0.1, 0.25, 0.5, 1.0]),
    )
    summary["mode"] = args.mode if args.snap_tolerance is None else "custom"
    summary["snap_tolerance"] = (
        dict(snap_tolerance) if isinstance(snap_tolerance, Mapping) else snap_tolerance
    )
    output_json = build_output_json(polygons, entities, runtime_seconds)

    (output_dir / "tokenization_output.json").write_text(json.dumps(output_json, indent=2), encoding="utf-8")
    (output_dir / "analysis_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_analysis_report(output_dir / "analysis_report.md", summary)

    drawable_entities = [entity for entity in entities if entity_extent(entity) is not None]
    full_extent = combine_extents([extent for entity in drawable_entities if (extent := entity_extent(entity)) is not None])
    target_entities = [entity for entity in drawable_entities if entity.family]
    target_extent = combine_extents([extent for entity in target_entities if (extent := entity_extent(entity)) is not None])

    if full_extent is not None:
        write_svg(output_dir / "raw_all.svg", full_extent, drawable_entities, [], entity_filter=None, polygon_filter=None)
    if target_extent is not None:
        write_svg(
            output_dir / "raw_target_families.svg",
            target_extent,
            target_entities,
            [],
            entity_filter=None,
            polygon_filter=None,
        )
        write_svg(
            output_dir / "extracted_overlay.svg",
            target_extent,
            target_entities,
            polygons,
            entity_filter=lambda entity: True,
            polygon_filter=lambda polygon: True,
        )
        for family in ["walls", "columns", "curtain_walls"]:
            family_entities = [entity for entity in target_entities if entity.family == family]
            family_polygons = [polygon for polygon in polygons if polygon.family == family]
            family_extent = combine_extents([extent for entity in family_entities if (extent := entity_extent(entity)) is not None])
            if family_extent is None:
                continue
            write_svg(
                output_dir / f"{family}.svg",
                family_extent,
                family_entities,
                family_polygons,
                entity_filter=lambda entity, family=family: entity.family == family,
                polygon_filter=lambda polygon, family=family: polygon.family == family,
            )

    suffix = format(report_tolerance, "g").replace(".", "_")
    write_wall_connectivity_svg(
        output_dir / f"wall_connectivity_snap_{suffix}.svg",
        graph_segments,
        tolerance=report_tolerance,
    )

    counts = family_polygon_counts(polygons)
    coverage = summary["target_primitive_totals"]["length_coverage_estimate"]
    print(f"Extracted {counts['walls']} walls, {counts['columns']} columns, "
          f"{counts['curtain_walls']} curtain walls in {runtime_seconds:.2f}s "
          f"({coverage:.1%} coverage)")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
