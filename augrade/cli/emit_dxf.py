"""CLI shim: ``python -m augrade.cli.emit_dxf``."""

from __future__ import annotations

from .. import emit_dxf as _mod


def main() -> None:
    _mod.main()


if __name__ == "__main__":
    main()
