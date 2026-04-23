"""Reusable DXF primitive-to-polygon extraction package.

The `augrade` package name is workspace-derived. The direct runnable
entry point is `tokenize_dxf.py`; this package exposes the same
extraction for dashboards, the merge lab, the REPL, and review scripts.

Single compute layer (dataset) with multiple views:
- DXF-native review: normalize + extract + emit_dxf
- Provenance-first review: dashboard + merge lab
- Interactive: repl
"""

__version__ = "0.1.0"
