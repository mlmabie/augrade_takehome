#!/usr/bin/env python3
"""
Layer normalization, provenance tracking, and anomaly detection for DXF polygon extraction.

Prepares raw DXF layer data for graph compilation by:
  1. Parsing layer names against AIA/NCS grammar
  2. Detecting and categorizing anomalies (encoding, naming, spatial, cross-classification)
  3. Proposing merge groups with empirical evidence (spatial overlap, entity-type similarity)
  4. Generating a provenance table and action log for auditability
  5. Producing a healed layer map that the extraction pipeline consumes

Every transformation is logged. Nothing is silently collapsed.

Usage:
    python normalize_layers.py <input.dxf> [--output-dir out/] [--auto-heal] [--strict]

    --auto-heal   Apply all LOW-severity fixes automatically (unicode normalization, etc.)
    --strict      Raise on any anomaly instead of logging (for CI / validation runs)
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from augrade.provenance import bbox_overlap_pct as _bbox_overlap_pct
from tokenize_dxf import FAMILY_LAYER_MAP as FAMILY_LAYERS

# ---------------------------------------------------------------------------
# AIA Grammar
# ---------------------------------------------------------------------------

class Discipline(Enum):
    A = "Architectural"
    S = "Structural"
    E = "Electrical"
    P = "Plumbing"
    GR = "Group/Block"
    UNKNOWN = "Unknown"


@dataclass
class LayerParse:
    """Parsed decomposition of a single layer name."""
    raw_name: str
    discipline: str          # A, S, E, P, GR, UNKNOWN
    major: str               # WALL, COLUMN, POST, GLAZING, GLASS, SILL, ...
    material: str            # STEEL, CONCRETE, or ""
    qualifier: str           # EXTERNAL, FULL, MULLION, variant 1, ...
    status: str              # HATCH or ""
    family: Optional[str]    # walls, columns, curtain_walls, or None
    anomalies: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Anomaly tracking
# ---------------------------------------------------------------------------

class Severity(Enum):
    LOW = "low"          # auto-healable (unicode, whitespace)
    MEDIUM = "medium"    # needs human judgment (merge decisions, cross-classification)
    HIGH = "high"        # structural ambiguity (unknown layers, missing data)


@dataclass
class Anomaly:
    layer: str
    category: str           # encoding, naming, spatial, cross_classification, missing, typo
    severity: Severity
    description: str
    proposed_action: str    # what the tool would do if auto-healing
    healed: bool = False    # whether the action was applied


@dataclass
class MergeGroup:
    """A proposed or confirmed merge of layers for geometric extraction."""
    family: str
    layers: List[str]
    relationship: str       # complementary, disjoint_zones, identical, superset
    spatial_overlap_pct: float
    shared_entity_types: List[str]
    evidence: str
    confirmed: bool = False


@dataclass
class ProvenanceRecord:
    """Per-entity provenance for the residual table."""
    entity_handle: str
    raw_layer: str
    healed_layer: str       # after unicode/whitespace normalization
    family: str
    entity_type: str
    bbox: Optional[Tuple[float, float, float, float]]


@dataclass
class NormalizationResult:
    """Full output of the normalization step."""
    layer_parses: List[LayerParse]
    anomalies: List[Anomaly]
    merge_groups: List[MergeGroup]
    layer_map: Dict[str, str]          # raw_layer -> healed_layer
    id_prefix_map: Dict[str, str]      # raw_layer -> polygon ID prefix
    provenance: List[ProvenanceRecord]
    actions_log: List[str]


# ---------------------------------------------------------------------------
# Family assignment (from task spec) — canonical source is tokenize_dxf.FAMILY_LAYER_MAP
# ---------------------------------------------------------------------------

HATCH_COMPANIONS: Dict[str, str] = {
    "A-EXTERNAL WALL HATCH": "A-EXTERNAL WALL",
    "A-MEZZANINE WALL FULL HATCH": "A-MEZZANINE WALL FULL",
    "A-WALL 1 HATCH": "A-WALL 1",
    "A-WALL 2 HATCH": "A-WALL 2",
    "S-COLUMN HATCH": "S-COLUMN",
    "S-CONCRETE COLUMN HATCH": "S-CONCRETE COLUMN",
    "S-STEEL COLUMN HATCH": "S-STEEL COLUMN",
}

# Canonical source for these maps is tokenize_dxf
from tokenize_dxf import LAYER_ID_PREFIX as ID_PREFIX_MAP
from tokenize_dxf import FAMILY_ID_FALLBACK as _FAMILY_ID_FALLBACK

MATERIALS = {"STEEL", "CONCRETE"}
LOCATIONS = {"EXTERNAL", "INTERNAL", "MEZZANINE", "PARTITION"}
QUALIFIERS = {
    "FULL", "FINISH", "MULLION", "ARRAY", "PANEL", "PARAPET",
    "NICHE", "PROTECTION", "SILL",
}


# ---------------------------------------------------------------------------
# Core: parse a layer name against AIA grammar
# ---------------------------------------------------------------------------

def parse_layer_name(raw: str, family_lookup: Dict[str, str]) -> LayerParse:
    anomalies: List[str] = []

    # Detect unicode encoding issues
    cleaned = raw
    for i, ch in enumerate(raw):
        if ord(ch) > 127:
            anomalies.append(f"non-ASCII U+{ord(ch):04X} at pos {i}")
            cleaned = cleaned.replace(ch, "-")

    # Split discipline
    if cleaned.startswith("GR_"):
        discipline = "GR"
        remainder = cleaned[3:].lstrip("-").strip()
    elif "-" in cleaned:
        parts = cleaned.split("-", 1)
        discipline = parts[0].strip().upper()
        # Normalize internal hyphens to spaces so "GLAZING-FULL" parses as major=GLAZING qualifier=FULL
        remainder = parts[1].replace("-", " ").strip()
    else:
        discipline = "UNKNOWN"
        remainder = cleaned
        anomalies.append("no discipline prefix")

    tokens = remainder.upper().split()

    # Extract major element type
    major_candidates = ["WALL", "COLUMN", "POST", "GLAZING", "GLASS", "SILL",
                        "FLOOR", "DOOR", "BEAM", "STAIR", "CEILING", "WINDOW"]
    major = ""
    for mc in major_candidates:
        if mc in tokens:
            major = mc
            break
    if not major and tokens:
        major = tokens[0]

    # Extract material, qualifier, status
    material = ""
    qualifiers = []
    status = ""
    for t in tokens:
        if t == major:
            continue
        if t in MATERIALS:
            material = t
        elif t == "HATCH":
            status = "HATCH"
        elif t in LOCATIONS:
            qualifiers.append(t)
        elif t in QUALIFIERS:
            qualifiers.append(t)
        elif re.match(r"^\d+$", t):
            qualifiers.append(f"v{t}")
        else:
            qualifiers.append(t)

    family = family_lookup.get(raw)

    return LayerParse(
        raw_name=raw,
        discipline=discipline,
        major=major,
        material=material,
        qualifier=" ".join(qualifiers),
        status=status,
        family=family,
        anomalies=anomalies,
    )


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def detect_anomalies(
    layer_names: List[str],
    layer_entity_types: Dict[str, Set[str]],
    layer_bboxes: Dict[str, Tuple[float, float, float, float]],
    family_lookup: Dict[str, str],
) -> List[Anomaly]:
    anomalies: List[Anomaly] = []

    for name in layer_names:
        # 1. Unicode encoding
        for i, ch in enumerate(name):
            if ord(ch) > 127:
                anomalies.append(Anomaly(
                    layer=name,
                    category="encoding",
                    severity=Severity.LOW,
                    description=f"Non-ASCII character U+{ord(ch):04X} at position {i} (likely non-breaking hyphen from Word/PDF paste)",
                    proposed_action=f"Replace U+{ord(ch):04X} with ASCII hyphen U+002D",
                ))

        # 2. Suspected typos (only flag names that DON'T have the correct prefix)
        upper = name.upper()
        if "URNITURE" in upper and "FURNITURE" not in upper:
            anomalies.append(Anomaly(
                layer=name,
                category="typo",
                severity=Severity.LOW,
                description="Likely typo: 'URNITURE' should be 'FURNITURE' (missing F)",
                proposed_action="Log only — not a target layer",
            ))

    # 3. Space vs hyphen variants (the glazing pairs)
    seen_canonical: Dict[str, List[str]] = defaultdict(list)
    for name in layer_names:
        canonical = re.sub(r"[-\s]+", " ", name.upper()).strip()
        seen_canonical[canonical].append(name)

    for canonical, variants in seen_canonical.items():
        if len(variants) > 1:
            # Check if they have the same or different spatial/type profiles
            types_match = True
            bboxes_overlap = True
            type_sets = [layer_entity_types.get(v, set()) for v in variants]
            if len(type_sets) >= 2 and type_sets[0] != type_sets[1]:
                types_match = False

            bb = [layer_bboxes.get(v) for v in variants]
            if all(b is not None for b in bb) and len(bb) >= 2:
                overlap = _bbox_overlap_pct(bb[0], bb[1])
                if overlap < 0.1:
                    bboxes_overlap = False

            if not types_match or not bboxes_overlap:
                severity = Severity.MEDIUM
                desc = (
                    f"Naming variants {variants} canonicalize to '{canonical}' "
                    f"but differ: entity_types_match={types_match}, "
                    f"spatial_overlap={'yes' if bboxes_overlap else 'NO (disjoint zones)'}. "
                    f"This is likely an authorship/phase boundary, not a typo."
                )
                action = "Pool into same family for extraction but preserve raw layer in source_layers"
            else:
                severity = Severity.LOW
                desc = f"Naming variants {variants} canonicalize to '{canonical}' with matching profiles."
                action = "Safe to treat as equivalent"

            anomalies.append(Anomaly(
                layer=variants[0],
                category="naming",
                severity=severity,
                description=desc,
                proposed_action=action,
            ))

    # 4. Cross-classification (A-WALL SILL in glazing family)
    for name in layer_names:
        family = family_lookup.get(name)
        if family and "WALL" in name.upper() and family != "walls":
            anomalies.append(Anomaly(
                layer=name,
                category="cross_classification",
                severity=Severity.MEDIUM,
                description=f"Layer contains 'WALL' but assigned to '{family}' family. Architecturally correct (sills belong to glazing) but may confuse downstream consumers.",
                proposed_action="Keep in assigned family; add cross_ref tag",
            ))

    # 5. Cross-discipline (S- prefix in walls family)
    for name in layer_names:
        family = family_lookup.get(name)
        if family == "walls" and name.startswith("S-"):
            anomalies.append(Anomaly(
                layer=name,
                category="cross_classification",
                severity=Severity.MEDIUM,
                description="Structural discipline layer in architectural walls family. Same physical element viewed from different engineering concern.",
                proposed_action="Keep in walls family; preserve S- discipline in polygon ID prefix",
            ))

    # 6. Missing target layers
    all_target = {l for layers in FAMILY_LAYERS.values() for l in layers}
    present = set(layer_names)
    for missing in sorted(all_target - present):
        anomalies.append(Anomaly(
            layer=missing,
            category="missing",
            severity=Severity.HIGH,
            description=f"Target layer '{missing}' not found in DXF file",
            proposed_action="Log warning, continue without this layer",
        ))

    return anomalies



# ---------------------------------------------------------------------------
# Merge group detection
# ---------------------------------------------------------------------------

def detect_merge_groups(
    layer_entity_types: Dict[str, Set[str]],
    layer_bboxes: Dict[str, Tuple[float, float, float, float]],
    family_lookup: Dict[str, str],
) -> List[MergeGroup]:
    groups: List[MergeGroup] = []

    # Group layers by family
    by_family: Dict[str, List[str]] = defaultdict(list)
    for layer, family in family_lookup.items():
        by_family[family].append(layer)

    for family, layers in by_family.items():
        # Check all pairs within family
        for i, a in enumerate(layers):
            for b in layers[i + 1:]:
                a_bb = layer_bboxes.get(a)
                b_bb = layer_bboxes.get(b)
                if a_bb is None or b_bb is None:
                    continue

                overlap = _bbox_overlap_pct(a_bb, b_bb)
                a_types = layer_entity_types.get(a, set())
                b_types = layer_entity_types.get(b, set())
                shared = sorted(a_types & b_types)

                # Only report noteworthy relationships
                canonical_a = re.sub(r"[-\s]+", " ", a.upper()).strip()
                canonical_b = re.sub(r"[-\s]+", " ", b.upper()).strip()
                if canonical_a != canonical_b:
                    continue  # only flag naming variants

                if overlap < 0.1 and not shared:
                    relationship = "disjoint_zones"
                    evidence = f"Spatially disjoint (overlap={overlap:.0%}), different entity types ({sorted(a_types)} vs {sorted(b_types)}). Likely different drafting phases/zones."
                elif overlap > 0.3 and not shared:
                    relationship = "complementary"
                    evidence = f"Same region (overlap={overlap:.0%}) but different entity types ({sorted(a_types)} vs {sorted(b_types)}). Same elements drawn with different conventions."
                elif overlap > 0.5 and shared:
                    relationship = "overlapping"
                    evidence = f"Significant overlap ({overlap:.0%}) with shared types {shared}. May be duplicates or revisions."
                else:
                    continue

                groups.append(MergeGroup(
                    family=family,
                    layers=sorted([a, b]),
                    relationship=relationship,
                    spatial_overlap_pct=round(overlap, 3),
                    shared_entity_types=shared,
                    evidence=evidence,
                ))

    return groups


# ---------------------------------------------------------------------------
# Polygon ID generation
# ---------------------------------------------------------------------------

def generate_polygon_id(
    source_layers: List[str],
    family: str,
    index: int,
) -> str:
    """Generate an AIA-grammar-aware polygon ID from source layers."""
    if len(source_layers) == 1:
        prefix = ID_PREFIX_MAP.get(source_layers[0])
        if prefix:
            return f"{prefix}_{index:04d}"

    # Multi-layer: use the most specific layer's prefix + multi tag
    for layer in source_layers:
        prefix = ID_PREFIX_MAP.get(layer)
        if prefix:
            return f"{prefix}_multi_{index:04d}"

    # Fallback for unknown layers on second test file
    return f"{_FAMILY_ID_FALLBACK.get(family, 'unk')}_{index:04d}"


# ---------------------------------------------------------------------------
# Healing: apply low-severity fixes
# ---------------------------------------------------------------------------

def build_layer_map(
    layer_names: List[str],
    anomalies: List[Anomaly],
    auto_heal: bool,
) -> Tuple[Dict[str, str], List[str]]:
    """Build raw_layer -> healed_layer map. Marks healed anomalies in-place. Returns (map, actions_log)."""
    layer_map: Dict[str, str] = {}
    actions: List[str] = []

    # Index encoding anomalies by layer for marking
    encoding_anomalies: Dict[str, List[Anomaly]] = defaultdict(list)
    for a in anomalies:
        if a.category == "encoding":
            encoding_anomalies[a.layer].append(a)

    for name in layer_names:
        healed = name
        # Unicode normalization
        changed = False
        for ch in name:
            if ord(ch) > 127:
                healed = healed.replace(ch, "-")
                changed = True
        if changed:
            if auto_heal:
                layer_map[name] = healed
                actions.append(f"HEALED [encoding] '{name}' -> '{healed}' (unicode hyphen normalized)")
                # Mark the corresponding anomaly objects as healed
                for a in encoding_anomalies.get(name, []):
                    a.healed = True
            else:
                layer_map[name] = name  # keep original
                actions.append(f"FLAGGED [encoding] '{name}' has non-ASCII chars (use --auto-heal to fix)")
        else:
            layer_map[name] = name

    return layer_map, actions


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_normalization(dxf_path: Path, output_dir: Path, auto_heal: bool = False, strict: bool = False) -> NormalizationResult:
    """Run the full normalization pipeline on a DXF file."""
    try:
        import ezdxf
    except ImportError:
        print("ezdxf required: uv pip install ezdxf", file=sys.stderr)
        sys.exit(1)

    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    # Gather raw layer statistics
    all_layers = sorted(set(e.dxf.layer for e in msp))
    layer_entity_types: Dict[str, Set[str]] = defaultdict(set)
    layer_counts: Dict[str, int] = Counter()
    layer_points: Dict[str, List[Tuple[float, float]]] = defaultdict(list)

    for e in msp:
        layer = e.dxf.layer
        layer_entity_types[layer].add(e.dxftype())
        layer_counts[layer] += 1
        # Collect points for bbox
        try:
            if e.dxftype() == "LINE":
                layer_points[layer].append((e.dxf.start[0], e.dxf.start[1]))
                layer_points[layer].append((e.dxf.end[0], e.dxf.end[1]))
            elif e.dxftype() == "LWPOLYLINE":
                for pt in e.get_points(format="xy"):
                    layer_points[layer].append((pt[0], pt[1]))
            elif e.dxftype() == "CIRCLE":
                layer_points[layer].append((e.dxf.center[0], e.dxf.center[1]))
            elif e.dxftype() == "INSERT":
                layer_points[layer].append((e.dxf.insert[0], e.dxf.insert[1]))
        except Exception:
            pass

    layer_bboxes: Dict[str, Tuple[float, float, float, float]] = {}
    for layer, pts in layer_points.items():
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            layer_bboxes[layer] = (min(xs), min(ys), max(xs), max(ys))

    # Build family lookup
    family_lookup: Dict[str, str] = {}
    for family, layers in FAMILY_LAYERS.items():
        for layer in layers:
            family_lookup[layer] = family

    # Parse layer names
    layer_parses = [parse_layer_name(name, family_lookup) for name in all_layers]

    # Detect anomalies
    anomalies = detect_anomalies(
        all_layers, layer_entity_types, layer_bboxes, family_lookup
    )

    if strict and anomalies:
        for a in anomalies:
            print(f"STRICT [{a.severity.value}] [{a.category}] {a.layer}: {a.description}", file=sys.stderr)
        sys.exit(1)

    # Detect merge groups
    merge_groups = detect_merge_groups(layer_entity_types, layer_bboxes, family_lookup)

    # Build healing map
    layer_map, actions_log = build_layer_map(all_layers, anomalies, auto_heal)

    # Build provenance (lightweight — full provenance built during extraction)
    provenance: List[ProvenanceRecord] = []
    for e in msp:
        layer = e.dxf.layer
        family = family_lookup.get(layer)
        if family is None:
            continue
        provenance.append(ProvenanceRecord(
            entity_handle=str(e.dxf.handle),
            raw_layer=layer,
            healed_layer=layer_map.get(layer, layer),
            family=family,
            entity_type=e.dxftype(),
            bbox=None,  # populated per-entity during extraction
        ))

    return NormalizationResult(
        layer_parses=layer_parses,
        anomalies=anomalies,
        merge_groups=merge_groups,
        layer_map=layer_map,
        id_prefix_map=dict(ID_PREFIX_MAP),
        provenance=provenance,
        actions_log=actions_log,
    )


def write_report(result: NormalizationResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Anomaly report
    report_lines = ["# Layer Normalization Report", ""]

    report_lines.append("## Anomalies")
    report_lines.append("")
    if not result.anomalies:
        report_lines.append("No anomalies detected.")
    for a in sorted(result.anomalies, key=lambda x: (x.severity.value, x.category)):
        icon = {"low": ".", "medium": "!", "high": "X"}[a.severity.value]
        healed_tag = " [HEALED]" if a.healed else ""
        report_lines.append(f"  [{icon}] [{a.severity.value:6s}] [{a.category:20s}] {a.layer}")
        report_lines.append(f"      {a.description}")
        report_lines.append(f"      -> {a.proposed_action}{healed_tag}")
        report_lines.append("")

    report_lines.append("## Merge Groups")
    report_lines.append("")
    if not result.merge_groups:
        report_lines.append("No merge groups detected.")
    for mg in result.merge_groups:
        report_lines.append(f"  [{mg.family}] {mg.layers} — {mg.relationship}")
        report_lines.append(f"      spatial_overlap: {mg.spatial_overlap_pct:.0%}")
        report_lines.append(f"      shared_types: {mg.shared_entity_types}")
        report_lines.append(f"      {mg.evidence}")
        report_lines.append("")

    report_lines.append("## Actions Taken")
    report_lines.append("")
    if not result.actions_log:
        report_lines.append("No actions taken.")
    for action in result.actions_log:
        report_lines.append(f"  {action}")

    report_lines.append("")
    report_lines.append("## ID Prefix Map")
    report_lines.append("")
    report_lines.append("| Raw Layer | Polygon ID Prefix |")
    report_lines.append("|-----------|------------------|")
    for layer, prefix in sorted(result.id_prefix_map.items()):
        report_lines.append(f"| `{layer}` | `{prefix}` |")

    (output_dir / "normalization_report.md").write_text("\n".join(report_lines), encoding="utf-8")

    # Machine-readable JSON
    json_output = {
        "anomalies": [
            {
                "layer": a.layer,
                "category": a.category,
                "severity": a.severity.value,
                "description": a.description,
                "proposed_action": a.proposed_action,
                "healed": a.healed,
            }
            for a in result.anomalies
        ],
        "merge_groups": [
            {
                "family": mg.family,
                "layers": mg.layers,
                "relationship": mg.relationship,
                "spatial_overlap_pct": mg.spatial_overlap_pct,
                "shared_entity_types": mg.shared_entity_types,
                "evidence": mg.evidence,
            }
            for mg in result.merge_groups
        ],
        "layer_map": result.layer_map,
        "id_prefix_map": result.id_prefix_map,
        "actions_log": result.actions_log,
        "layer_parses": [
            {
                "raw_name": lp.raw_name,
                "discipline": lp.discipline,
                "major": lp.major,
                "material": lp.material,
                "qualifier": lp.qualifier,
                "status": lp.status,
                "family": lp.family,
                "anomalies": lp.anomalies,
            }
            for lp in result.layer_parses
            if lp.family is not None  # only target layers
        ],
        "provenance_count": len(result.provenance),
        "provenance_sample": [
            {
                "entity_handle": p.entity_handle,
                "raw_layer": p.raw_layer,
                "healed_layer": p.healed_layer,
                "family": p.family,
                "entity_type": p.entity_type,
            }
            for p in result.provenance[:50]  # first 50 for inspection
        ],
    }
    (output_dir / "normalization.json").write_text(
        json.dumps(json_output, indent=2), encoding="utf-8"
    )

    # Full provenance table as separate file (can be large)
    provenance_records = [
        {
            "entity_handle": p.entity_handle,
            "raw_layer": p.raw_layer,
            "healed_layer": p.healed_layer,
            "family": p.family,
            "entity_type": p.entity_type,
        }
        for p in result.provenance
    ]
    (output_dir / "provenance.json").write_text(
        json.dumps(provenance_records, indent=None), encoding="utf-8"  # compact, one line per record is fine
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Layer normalization and anomaly detection for DXF polygon extraction."
    )
    parser.add_argument("input_dxf", type=Path, help="Path to DXF file")
    parser.add_argument("--output-dir", type=Path, default=Path("out"), help="Output directory")
    parser.add_argument("--auto-heal", action="store_true", help="Apply LOW-severity fixes automatically")
    parser.add_argument("--strict", action="store_true", help="Raise on any anomaly")
    args = parser.parse_args()

    result = run_normalization(args.input_dxf, args.output_dir, args.auto_heal, args.strict)
    write_report(result, args.output_dir)

    # Summary to stdout
    n_anomalies = len(result.anomalies)
    n_high = sum(1 for a in result.anomalies if a.severity == Severity.HIGH)
    n_medium = sum(1 for a in result.anomalies if a.severity == Severity.MEDIUM)
    n_low = sum(1 for a in result.anomalies if a.severity == Severity.LOW)
    n_merges = len(result.merge_groups)
    n_actions = len(result.actions_log)
    n_provenance = len(result.provenance)

    print(f"Normalization complete.")
    print(f"  Anomalies: {n_anomalies} ({n_high} high, {n_medium} medium, {n_low} low)")
    print(f"  Merge groups: {n_merges}")
    print(f"  Actions: {n_actions}")
    print(f"  Provenance records: {n_provenance}")
    print(f"  Output: {args.output_dir}/normalization_report.md")
    print(f"          {args.output_dir}/normalization.json")
    print(f"          {args.output_dir}/provenance.json")


if __name__ == "__main__":
    main()
