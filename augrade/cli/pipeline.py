"""CLI shim: ``python -m augrade.cli.pipeline``."""

from __future__ import annotations

from .. import pipeline as _pipeline


def main() -> None:
    _pipeline.main()


if __name__ == "__main__":
    main()
