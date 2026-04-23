#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import tokenize_dxf as td

from .review import dashboard as build_dashboard
from .review import merge_lab as build_merge_lab
from . import provenance as pu
from .extract import run_extraction


def write_tokenization_bundle(input_dxf: Path, output_dir: Path, snap_tolerance) -> dict:
    extraction = run_extraction(input_dxf, snap_tolerance)
    entities = extraction.entities
    polygons = extraction.polygons
    graph_segments = extraction.graph_segments
    report_tolerance = extraction.scalar_snap_tolerance

    summary = td.build_analysis_summary(
        entities=entities,
        polygons=polygons,
        runtime_seconds=extraction.runtime_seconds,
        snap_stats=td.compute_snap_stats(entities, wall_tolerances=[0.1, 0.25, 0.5, 1.0]),
    )
    summary["snap_tolerance"] = (
        dict(snap_tolerance) if isinstance(snap_tolerance, dict) else snap_tolerance
    )
    summary["scalar_snap_tolerance"] = report_tolerance
    output_json = td.build_output_json(polygons, entities, runtime_seconds=summary["runtime_seconds"])
    provenance = pu.build_provenance_index(entities)

    (output_dir / "tokenization_output.json").write_text(json.dumps(output_json, indent=2), encoding="utf-8")
    (output_dir / "analysis_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    td.write_analysis_report(output_dir / "analysis_report.md", summary)
    (output_dir / "provenance_index.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")

    drawable_entities = [entity for entity in entities if td.entity_extent(entity) is not None]
    full_extent = td.combine_extents([extent for entity in drawable_entities if (extent := td.entity_extent(entity)) is not None])
    target_entities = [entity for entity in drawable_entities if entity.family]
    target_extent = td.combine_extents([extent for entity in target_entities if (extent := td.entity_extent(entity)) is not None])

    if full_extent is not None:
        td.write_svg(output_dir / "raw_all.svg", full_extent, drawable_entities, [], entity_filter=None, polygon_filter=None)
    if target_extent is not None:
        td.write_svg(output_dir / "raw_target_families.svg", target_extent, target_entities, [], entity_filter=None, polygon_filter=None)
        td.write_svg(output_dir / "extracted_overlay.svg", target_extent, target_entities, polygons, entity_filter=lambda entity: True, polygon_filter=lambda polygon: True)
        for family in ["walls", "columns", "curtain_walls"]:
            family_entities = [entity for entity in target_entities if entity.family == family]
            family_polygons = [polygon for polygon in polygons if polygon.family == family]
            family_extent = td.combine_extents([extent for entity in family_entities if (extent := td.entity_extent(entity)) is not None])
            if family_extent is None:
                continue
            td.write_svg(
                output_dir / f"{family}.svg",
                family_extent,
                family_entities,
                family_polygons,
                entity_filter=lambda entity, family=family: entity.family == family,
                polygon_filter=lambda polygon, family=family: polygon.family == family,
            )
    suffix = format(report_tolerance, "g").replace(".", "_")
    td.write_wall_connectivity_svg(
        output_dir / f"wall_connectivity_snap_{suffix}.svg",
        graph_segments,
        tolerance=report_tolerance,
    )

    return {
        "extraction": extraction,
        "polygon_counts": {family: len([polygon for polygon in polygons if polygon.family == family]) for family in ["walls", "columns", "curtain_walls"]},
        "provenance": provenance["family_summaries"],
    }


def write_merge_lab_bundle(input_dxf: Path, output_dir: Path, snap_tolerance: float, extraction=None) -> None:
    dataset = build_merge_lab.build_dataset(input_dxf, snap_tolerance, extraction=extraction)
    (output_dir / "merge_lab_data.json").write_text(json.dumps(dataset, indent=2), encoding="utf-8")
    (output_dir / "merge_lab.html").write_text(build_merge_lab.build_html(dataset), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the full HITL analysis bundle: extraction, provenance, dashboard, and merge lab.")
    parser.add_argument("input_dxf", type=Path, help="Source DXF file.")
    parser.add_argument("output_dir", type=Path, help="Directory for all generated artifacts.")
    parser.add_argument(
        "--mode",
        choices=sorted(td.SNAP_TOLERANCE_MODES),
        default="conservative",
        help="Named extraction preset. conservative=0.5, liberal=0.75. Overridden by --snap-tolerance.",
    )
    parser.add_argument(
        "--snap-tolerance",
        type=str,
        default=None,
        help=(
            "Advanced override: scalar, per-family map "
            "('walls=0.5,columns=0.25,curtain_walls=0.35'), or 'adaptive'."
        ),
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve once against parsed entities so every caller (dashboard,
    # merge lab, connectivity SVG, manifest) sees the same value.
    entities = list(td.iter_entities(args.input_dxf))
    if args.snap_tolerance is not None:
        snap_tolerance = td.resolve_snap_tolerance(args.snap_tolerance, entities=entities)
        mode_label = "custom"
    else:
        snap_tolerance = td.SNAP_TOLERANCE_MODES[args.mode]
        mode_label = args.mode
    scalar_snap = td.snap_tolerance_for_report(snap_tolerance)
    suffix = format(scalar_snap, "g").replace(".", "_")

    token_summary = write_tokenization_bundle(args.input_dxf, args.output_dir, snap_tolerance)
    extraction = token_summary["extraction"]
    build_dashboard.build_dashboard(args.input_dxf, args.output_dir, scalar_snap, extraction=extraction)
    write_merge_lab_bundle(args.input_dxf, args.output_dir, scalar_snap, extraction=extraction)

    manifest = {
        "input_file": str(args.input_dxf),
        "mode": mode_label,
        "snap_tolerance": (
            dict(snap_tolerance) if isinstance(snap_tolerance, dict) else snap_tolerance
        ),
        "scalar_snap_tolerance": scalar_snap,
        "polygon_counts": token_summary["polygon_counts"],
        "provenance_summary": token_summary["provenance"],
        "artifacts": [
            "tokenization_output.json",
            "analysis_summary.json",
            "analysis_report.md",
            "provenance_index.json",
            "raw_all.svg",
            "raw_target_families.svg",
            "extracted_overlay.svg",
            "walls.svg",
            "columns.svg",
            "curtain_walls.svg",
            f"wall_connectivity_snap_{suffix}.svg",
            "dashboard.html",
            "merge_lab.html",
            "merge_lab_data.json",
        ],
    }
    (args.output_dir / "pipeline_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("HITL pipeline complete.")
    print(f"  Output directory: {args.output_dir}")
    print(f"  Polygon counts: {manifest['polygon_counts']}")
    print(f"  Dashboard: {args.output_dir / 'dashboard.html'}")
    print(f"  Merge lab: {args.output_dir / 'merge_lab.html'}")


if __name__ == "__main__":
    main()
