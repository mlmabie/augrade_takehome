"""CLI shim: ``python -m augrade.cli.normalize``."""

from __future__ import annotations

from .. import normalize as _mod


def main() -> None:
    _mod.main()


if __name__ == "__main__":
    main()
