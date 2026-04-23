# Layer Normalization and Provenance-Preserving Merge Strategy

## The Problem

The task spec notes: "some layer names appear twice with subtle differences (for example A-GLAZING MULLION and A-GLAZING-MULLION). You may normalize or merge layer names."

The naive response is `name.replace('-', ' ')` and move on. That's wrong. Layer name variation in architectural DXF files is not noise — it can encode schema versions, drafting phases, or authorship boundaries. The question is whether this particular dataset contains that signal, and whether the merge strategy preserves enough provenance to recover it later.

## Empirical Findings

### Merge Candidate 1: `A-GLAZING MULLION` vs `A-GLAZING-MULLION`

| Property | `A-GLAZING MULLION` | `A-GLAZING-MULLION` |
|----------|---------------------|---------------------|
| Entity count | 546 | 587 |
| Entity types | LINE only | LWPOLYLINE only |
| Spatial extent (X) | 7.0 – 17810.1 | 7.0 – 17555.5 |
| Spatial extent (Y) | 789.0 – 14600.4 | 168.0 – 14345.8 |
| Centroid | (9850, 5900) | (8358, 5189) |

**Finding:** These layers overlap spatially but use entirely different entity types for the same physical elements. One drafter (or CAD standard) drew mullions as raw LINE segments; another drew them as closed LWPOLYLINEs. This is not a typo — it's a schema-version or authorship boundary encoded in the layer name.

### Merge Candidate 2: `A-GLAZING FULL` vs `A-GLAZING-FULL`

| Property | `A-GLAZING FULL` | `A-GLAZING-FULL` |
|----------|------------------|------------------|
| Entity count | 2420 | 1999 |
| Entity types | LINE, LWPOLYLINE, INSERT | LINE only |
| Spatial extent (X) | 19294.5 – 25379.4 | 7.0 – 17853.2 |
| Spatial extent (Y) | 15862.6 – 18068.5 | 168.8 – 14601.8 |
| Centroid | (22122, 16980) | (11215, 7626) |

**Finding:** These layers occupy **completely disjoint spatial regions**. `A-GLAZING FULL` covers the upper-right zone (X: 19k–25k); `A-GLAZING-FULL` covers the main floor area (X: 7–17k). They also differ in entity richness: the space-variant has polylines and block inserts; the hyphen-variant is lines only. This is almost certainly two different drafting phases or sub-contractors working on different zones of the same building.

### HATCH Companion Layers

Four wall layers have HATCH companion layers that contain the same
physical elements drawn as filled regions. The solver enumerates these
layers explicitly in `FAMILY_LAYER_MAP["walls"]` and preserves the
companion layer names in `source_layers`.

| Target Layer | Companion Layer | Count | Entity Types |
|-------------|-----------------|-------|-------------|
| A-EXTERNAL WALL | A-EXTERNAL WALL HATCH | 24 | HATCH |
| A-MEZZANINE WALL FULL | A-MEZZANINE WALL FULL HATCH | 1301 | LINE, LWPOLYLINE, HATCH |
| A-WALL 1 | A-WALL 1 HATCH | 11 | HATCH |
| A-WALL 2 | A-WALL 2 HATCH | 126 | LINE, HATCH, LWPOLYLINE |

These represent the same architectural wall drawn on two layers: outline (target) and fill (companion). The HATCH boundaries are ground-truth polygon shapes.

### Non-Target Layers with Potential Signal

| Layer | Count | Types | Notes |
|-------|-------|-------|-------|
| A-WALL CONNECTION | 3663 | LINE, ELLIPSE | Wall-to-wall junctions — useful for merge decisions |
| A-WINDOW GLAZING | 180 | LWPOLYLINE, LINE, 3DFACE | Not in target scope but spatially co-located with glazing |
| GR_A-GLASS PANEL SUPPORT | 17200 | ARC, LINE, ELLIPSE, INSERT, CIRCLE | Massive layer — structural framing behind curtain walls |
| A-WALL-COLW | 77 | LINE, LWPOLYLINE, CIRCLE | Wall-column intersection details |

## The Strategy: Pool for Geometry, Tag for Provenance

### Principle

> Make the efficient ideal lossy transformation, but maintain residuals in a table.

The geometric extraction needs all primitives from a family pooled together — you can't polygonize `A-GLAZING FULL` and `A-GLAZING-FULL` separately because a single physical panel might have its outline on one layer and its fill on the other. But collapsing the layer names loses provenance that matters for debugging, auditing, and understanding drafting conventions.

### Implementation

**Step 1: Build the layer provenance table before any geometric processing.**

```python
layer_provenance = []

for entity in modelspace:
    if entity.dxf.layer in target_layers:
        layer_provenance.append({
            "raw_layer": entity.dxf.layer,
            "family": classify_family(entity.dxf.layer),
            "entity_type": entity.dxftype(),
            "entity_handle": entity.dxf.handle,
            "bbox": get_bbox(entity),  # spatial extent of this primitive
            "centroid": get_centroid(entity),
        })

provenance_df = pd.DataFrame(layer_provenance)
```

This table is the **residual**. Every downstream transformation can be traced back through it.

**Step 2: Detect merge groups empirically, not by string normalization.**

Instead of normalizing names, cluster layers by spatial overlap and entity-type similarity:

```python
merge_analysis = []

for family in ["walls", "columns", "glazing"]:
    family_layers = get_layers_for_family(family)
    for a, b in combinations(family_layers, 2):
        a_bbox = get_layer_bbox(a)
        b_bbox = get_layer_bbox(b)
        overlap = compute_bbox_overlap(a_bbox, b_bbox)
        a_types = get_entity_types(a)
        b_types = get_entity_types(b)
        type_overlap = a_types & b_types

        merge_analysis.append({
            "layer_a": a,
            "layer_b": b,
            "family": family,
            "spatial_overlap_pct": overlap,
            "shared_entity_types": type_overlap,
            "same_drafter_likely": overlap > 0.5 and len(type_overlap) > 0,
            "complementary_likely": overlap > 0.3 and len(type_overlap) == 0,
            "disjoint_zones": overlap < 0.1,
        })
```

This produces a merge report that says *why* layers were grouped, not just *that* they were.

**Step 3: Pool by family for geometric extraction.**

All target layers within a family go into a single primitive pool. The polygonize pass doesn't care about layer boundaries — it cares about geometric connectivity.

```python
for family in families:
    all_segments = []
    for layer in family.layers:
        segments = discretize_layer(layer)
        for seg in segments:
            seg.metadata["source_layer"] = layer  # tag before pooling
        all_segments.extend(segments)

    polygons = polygonize(unary_union(all_segments))
```

**Step 4: Back-attribute source layers to output polygons.**

After extraction, each polygon gets tagged with which raw layers contributed segments to it:

```python
for polygon in output_polygons:
    contributing_layers = set()
    for segment in all_segments:
        if polygon.boundary.distance(segment) < snap_tolerance:
            contributing_layers.add(segment.metadata["source_layer"])
    polygon.source_layers = sorted(contributing_layers)
```

A polygon with `source_layers: ["A-GLAZING FULL", "A-GLAZING-FULL"]` tells the reviewer this element spans two drafting conventions. A polygon with `source_layers: ["A-GLAZING-FULL"]` only tells the reviewer it came from the hyphen-variant zone.

**Step 5: Emit the provenance table alongside the JSON output.**

```json
{
  "polygons": { ... },
  "layer_provenance": {
    "merge_groups": [
      {
        "family": "glazing",
        "layers": ["A-GLAZING FULL", "A-GLAZING-FULL"],
        "relationship": "disjoint_zones",
        "spatial_overlap_pct": 0.0,
        "shared_entity_types": [],
        "note": "Occupy non-overlapping spatial regions with different entity type profiles. Likely different drafting phases."
      },
      {
        "family": "glazing",
        "layers": ["A-GLAZING MULLION", "A-GLAZING-MULLION"],
        "relationship": "complementary",
        "spatial_overlap_pct": 0.72,
        "shared_entity_types": [],
        "note": "Same spatial region, different entity types (LINE vs LWPOLYLINE). Same elements drawn with different conventions."
      }
    ],
    "hatch_companions": [
      {
        "target_layer": "A-EXTERNAL WALL",
        "companion_layer": "A-EXTERNAL WALL HATCH",
        "companion_count": 24,
        "used_for": "validation"
      }
    ],
    "layer_statistics": [
      {
        "raw_layer": "A-GLAZING FULL",
        "family": "glazing",
        "entity_count": 2420,
        "entity_types": {"LINE": 2299, "LWPOLYLINE": 98, "INSERT": 23},
        "bbox": {"x_min": 19294.5, "x_max": 25379.4, "y_min": 15862.6, "y_max": 18068.5}
      }
    ]
  }
}
```

## Why This Matters

1. **Reversibility.** Any downstream consumer can reconstruct which raw primitives on which raw layers contributed to any output polygon. The lossy merge (family pooling) is efficient for extraction; the residual table makes it lossless for auditing.

2. **Generalization.** External DXFs may have similar layer names but different geometry and different drafting conventions. A naive normalizer tuned to this file's naming quirks will break. An empirical merge strategy that reports *spatial overlap* and *entity-type similarity* can surface file-specific naming conventions without hardcoding them.

3. **Signal preservation.** If the space-vs-hyphen distinction encodes drafting phase, sub-contractor, or schema version, that signal survives in the provenance table even though it was collapsed for geometric extraction. A future system could learn from this — for example, discovering that hyphen-variant layers tend to have higher drafting quality or different tolerance profiles.

4. **Debuggability.** When a polygon is wrong, the reviewer can check: which layers contributed? Were segments from different layers merged? Did a HATCH companion confirm or contradict the extracted shape? This is the difference between "the algorithm produced garbage" and "the algorithm correctly merged segments from two layers but one layer had a drafting error at this location."

## Summary

| Step | What Happens | Lossy? | Recoverable? |
|------|-------------|--------|-------------|
| Layer provenance table | Record raw layer, entity type, bbox per primitive | No | N/A — this is the ground truth |
| Merge group analysis | Cluster layers by spatial/type overlap | No | Full report emitted |
| Family pooling | Collapse layers into family pools | Yes — layer boundaries removed | Yes — via segment metadata tags |
| Polygonize | Extract closed polygons from pooled segments | Yes — primitives → polygons | Partially — via source_layer back-attribution |
| Back-attribution | Tag each polygon with contributing layers | No | N/A — restores provenance |

The full transformation is: **raw DXF → provenance table + family pools → polygons + source attribution + merge report**. The extraction is lossy by necessity (that's the whole point — compress primitives into polygons). The provenance chain makes it auditable.

## Tooling

This analysis is implemented in two scripts:

- **`normalize_layers.py`** — standalone normalization, anomaly detection, and merge-group analysis. Runs before extraction. Produces `normalization_report.md` (human-readable) and `normalization.json` (machine-readable). Supports `--auto-heal` for LOW-severity fixes and `--strict` for CI validation.
- **`tokenize_dxf.py`** — the extraction pipeline. Consumes the layer→family map and ID prefix scheme from the normalization step. Every output polygon gets an AIA-grammar-aware ID (e.g., `s_col_steel_0015`) and `source_layers` back-attribution.

See also:
- `tokenize_dxf.py::LAYER_ID_PREFIX` — current ID prefix scheme
