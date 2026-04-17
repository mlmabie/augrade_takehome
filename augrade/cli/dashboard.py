"""CLI shim: ``python -m augrade.cli.dashboard``."""

from __future__ import annotations

from .. import dashboard_html as _mod


def main() -> None:
    _mod.main()


if __name__ == "__main__":
    main()
