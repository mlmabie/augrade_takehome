"""Interactive augrade shell: ``python -m augrade.repl``.

Every command is a thin wrapper over the augrade library. No new logic lives
here; the REPL exists to make the library self-describing and to unify the
DXF-native review and provenance-first HITL paths behind one session state.
"""

from __future__ import annotations

import argparse
import cmd
import copy
import json
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from . import dataset as _ds
from . import merge as _merge
from . import normalize as _normalize


@dataclass
class SessionState:
    """Everything a session needs to remember between commands."""

    input_dxf: Optional[Path] = None
    snap_tolerance: float = 0.5
    output_dir: Path = field(default_factory=lambda: Path("out"))
    dataset: Optional[_ds.AnalysisDataset] = None
    normalization: Optional[object] = None
    rules: Dict[str, Dict[str, float]] = field(
        default_factory=lambda: copy.deepcopy(_merge.FAMILY_PRESETS)
    )
    labels: Dict[str, str] = field(default_factory=dict)


def _fmt_poly_count(dataset: _ds.AnalysisDataset) -> str:
    return ", ".join(
        f"{family}: {len(dataset.polygons_by_family[family])}"
        for family in _ds.FAMILIES
    )


def _parse_candidate_id(raw: str) -> tuple[str, int, int]:
    family, a, b = raw.split(":", 2)
    return family, int(a), int(b)


class AugradeShell(cmd.Cmd):
    intro = (
        "augrade REPL -- type 'help' for commands, 'quit' to exit.\n"
        "Start with:  open <dxf>  then  extract"
    )
    prompt = "augrade> "

    def __init__(self, state: Optional[SessionState] = None) -> None:
        super().__init__()
        self.state = state if state is not None else SessionState()

    def _require_dataset(self) -> Optional[_ds.AnalysisDataset]:
        if self.state.dataset is None:
            print("no dataset loaded -- run `extract` first")
            return None
        return self.state.dataset

    def do_open(self, arg: str) -> None:
        """open <dxf>    -- record the input DXF path for later commands"""
        parts = shlex.split(arg)
        if len(parts) != 1:
            print("usage: open <dxf>")
            return
        path = Path(parts[0])
        if not path.exists():
            print(f"file not found: {path}")
            return
        self.state.input_dxf = path
        self.state.dataset = None
        print(f"opened {path}")

    def do_normalize(self, arg: str) -> None:
        """normalize [--auto-heal | --strict]    -- run DXF layer normalization"""
        if self.state.input_dxf is None:
            print("no input -- run `open <dxf>` first")
            return
        parser = argparse.ArgumentParser(prog="normalize", add_help=False)
        parser.add_argument("--auto-heal", action="store_true")
        parser.add_argument("--strict", action="store_true")
        try:
            args = parser.parse_args(shlex.split(arg))
        except SystemExit:
            return
        self.state.output_dir.mkdir(parents=True, exist_ok=True)
        result = _normalize.run_normalization(
            self.state.input_dxf,
            self.state.output_dir,
            auto_heal=args.auto_heal,
            strict=args.strict,
        )
        self.state.normalization = result
        print(
            "normalize done -- "
            f"auto_heal={args.auto_heal} strict={args.strict}, see "
            f"{self.state.output_dir}"
        )

    def do_extract(self, arg: str) -> None:
        """extract [--snap 0.5]    -- extract polygons and build AnalysisDataset"""
        if self.state.input_dxf is None:
            print("no input -- run `open <dxf>` first")
            return
        parser = argparse.ArgumentParser(prog="extract", add_help=False)
        parser.add_argument("--snap", type=float, default=self.state.snap_tolerance)
        try:
            args = parser.parse_args(shlex.split(arg))
        except SystemExit:
            return
        self.state.snap_tolerance = args.snap
        self.state.dataset = _ds.build(
            self.state.input_dxf, args.snap, with_merge=True
        )
        print(
            f"extracted in {self.state.dataset.runtime_seconds:.2f}s -- "
            f"{_fmt_poly_count(self.state.dataset)}"
        )

    def do_status(self, arg: str) -> None:
        """status    -- print session state"""
        print(f"input_dxf       : {self.state.input_dxf}")
        print(f"snap_tolerance  : {self.state.snap_tolerance}")
        print(f"output_dir      : {self.state.output_dir}")
        print(f"dataset         : {'loaded' if self.state.dataset else 'none'}")
        print(f"normalization   : {'loaded' if self.state.normalization else 'none'}")
        print(f"labels          : {len(self.state.labels)} entries")
        if self.state.dataset is not None:
            print(f"polygons        : {_fmt_poly_count(self.state.dataset)}")

    def do_polys(self, arg: str) -> None:
        """polys count    -- count polygons by family"""
        dataset = self._require_dataset()
        if dataset is None:
            return
        if arg.strip() in ("", "count"):
            print(_fmt_poly_count(dataset))
        else:
            print("usage: polys count")

    def do_show(self, arg: str) -> None:
        """show <polygon-id>    -- print descriptor JSON for a polygon"""
        dataset = self._require_dataset()
        if dataset is None:
            return
        target = arg.strip()
        if not target:
            print("usage: show <polygon-id>")
            return
        assert dataset.descriptors_by_family is not None
        for family in _ds.FAMILIES:
            for descriptor in dataset.descriptors_by_family[family]:
                if descriptor["id"] == target:
                    print(json.dumps(descriptor, indent=2))
                    return
        print(f"polygon not found: {target}")

    def do_pair(self, arg: str) -> None:
        """pair <family>:<i>:<j>    -- show a candidate pair's metrics"""
        dataset = self._require_dataset()
        if dataset is None:
            return
        try:
            family, a, b = _parse_candidate_id(arg.strip())
        except ValueError:
            print("usage: pair <family>:<i>:<j>")
            return
        assert dataset.family_payloads is not None
        candidates = dataset.family_payloads[family]["candidates"]
        target_id = f"{family}:{a}:{b}"
        for cand in candidates:
            if cand["id"] == target_id:
                print(json.dumps(cand, indent=2))
                return
        print(f"pair not found: {target_id}")

    def do_rules(self, arg: str) -> None:
        """rules show <family>
        rules set <family>.<key> <value>"""
        parts = shlex.split(arg)
        if len(parts) >= 2 and parts[0] == "show":
            family = parts[1]
            if family not in self.state.rules:
                print(f"unknown family: {family}")
                return
            print(json.dumps(self.state.rules[family], indent=2))
            return
        if len(parts) == 3 and parts[0] == "set":
            key_path, value = parts[1], parts[2]
            if "." not in key_path:
                print("usage: rules set <family>.<key> <value>")
                return
            family, key = key_path.split(".", 1)
            if family not in self.state.rules:
                print(f"unknown family: {family}")
                return
            if key not in self.state.rules[family]:
                print(f"unknown key: {family}.{key}")
                return
            try:
                numeric = float(value)
            except ValueError:
                print(f"value must be numeric: {value}")
                return
            self.state.rules[family][key] = numeric
            print(f"set {family}.{key} = {numeric}")
            return
        print("usage: rules show <family> | rules set <family>.<key> <value>")

    def do_recompute(self, arg: str) -> None:
        """recompute merges <family>    -- rescore candidates for a family using current rules"""
        parts = shlex.split(arg)
        if len(parts) != 2 or parts[0] != "merges":
            print("usage: recompute merges <family>")
            return
        family = parts[1]
        dataset = self._require_dataset()
        if dataset is None:
            return
        if family not in _ds.FAMILIES:
            print(f"unknown family: {family}")
            return
        original = _merge.FAMILY_PRESETS[family]
        override = self.state.rules[family]
        _merge.FAMILY_PRESETS[family] = override
        try:
            payload = _merge.generate_family_data(
                family,
                dataset.polygons_by_family[family],
                dataset.entity_by_id,
                dataset.provenance,
            )
        finally:
            _merge.FAMILY_PRESETS[family] = original
        assert dataset.family_payloads is not None
        dataset.family_payloads[family] = payload
        assert dataset.descriptors_by_family is not None
        dataset.descriptors_by_family[family] = payload["polygons"]
        stats = payload["stats"]
        print(
            f"recomputed {family}: "
            f"{stats['candidate_count']} candidates, "
            f"{stats['recommended_count']} recommended"
        )

    def do_label(self, arg: str) -> None:
        """label {positive|negative|clear} <candidate-id>"""
        parts = shlex.split(arg)
        if len(parts) != 2 or parts[0] not in ("positive", "negative", "clear"):
            print("usage: label {positive|negative|clear} <candidate-id>")
            return
        action, cand_id = parts
        if action == "clear":
            self.state.labels.pop(cand_id, None)
            print(f"cleared label for {cand_id}")
        else:
            self.state.labels[cand_id] = action
            print(f"{action} -> {cand_id}  (total: {len(self.state.labels)})")

    def do_labels(self, arg: str) -> None:
        """labels export <path>
        labels import <path>"""
        parts = shlex.split(arg)
        if len(parts) != 2 or parts[0] not in ("export", "import"):
            print("usage: labels {export|import} <path>")
            return
        action, raw_path = parts
        path = Path(raw_path)
        if action == "export":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.state.labels, indent=2), encoding="utf-8")
            print(f"wrote {len(self.state.labels)} labels to {path}")
        else:
            if not path.exists():
                print(f"file not found: {path}")
                return
            self.state.labels = json.loads(path.read_text(encoding="utf-8"))
            print(f"loaded {len(self.state.labels)} labels from {path}")

    def do_emit(self, arg: str) -> None:
        """emit dashboard <dir>
        emit merge-lab <dir>
        emit dxf <path>
        emit bundle <dir>"""
        parts = shlex.split(arg)
        if len(parts) < 2:
            print("usage: emit {dashboard|merge-lab|dxf|bundle} <path>")
            return
        kind, target = parts[0], Path(parts[1])
        dataset = self._require_dataset()
        if dataset is None:
            return
        if kind == "dashboard":
            from . import dashboard_html

            target.mkdir(parents=True, exist_ok=True)
            (target / "dashboard_assets").mkdir(exist_ok=True)
            dashboard_html.render_dashboard(dataset, target)
            print(f"wrote dashboard to {target / 'dashboard.html'}")
            return
        if kind == "merge-lab":
            from . import merge_lab_html

            target.mkdir(parents=True, exist_ok=True)
            payload = _ds.merge_lab_payload(dataset)
            (target / "merge_lab_data.json").write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
            (target / "merge_lab.html").write_text(
                merge_lab_html.build_html(payload), encoding="utf-8"
            )
            print(f"wrote merge lab to {target / 'merge_lab.html'}")
            return
        if kind == "dxf":
            from . import emit_dxf

            assert self.state.input_dxf is not None
            assert dataset.descriptors_by_family is not None
            extraction_json = {
                "polygons": [
                    {
                        "polygon_id": descriptor["id"],
                        "family": family,
                        "vertices": [
                            {"x_coord": x, "y_coord": y}
                            for x, y in descriptor["vertices"]
                        ],
                        "source_layers": descriptor["source_layers"],
                    }
                    for family in _ds.FAMILIES
                    for descriptor in dataset.descriptors_by_family[family]
                ]
            }
            target.parent.mkdir(parents=True, exist_ok=True)
            emit_dxf.write_cleaned_dxf(
                self.state.input_dxf, extraction_json, target
            )
            print(f"wrote DXF to {target}")
            return
        if kind == "bundle":
            from . import pipeline as _pipeline

            assert self.state.input_dxf is not None
            target.mkdir(parents=True, exist_ok=True)
            _pipeline.write_tokenization_bundle(
                self.state.input_dxf, target, self.state.snap_tolerance
            )
            from . import dashboard_html, merge_lab_html

            dashboard_html.render_dashboard(dataset, target)
            payload = _ds.merge_lab_payload(dataset)
            (target / "merge_lab_data.json").write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
            (target / "merge_lab.html").write_text(
                merge_lab_html.build_html(payload), encoding="utf-8"
            )
            print(f"wrote full bundle to {target}")
            return
        print(f"unknown emit kind: {kind}")

    def do_quit(self, arg: str) -> bool:
        """quit    -- exit the REPL"""
        return True

    do_exit = do_quit
    do_EOF = do_quit

    def emptyline(self) -> bool:
        return False

    def default(self, line: str) -> None:
        print(f"unknown command: {line.split()[0]}  (type 'help')")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Interactive augrade shell -- unified REPL over the pipeline.",
    )
    parser.add_argument("--input", type=Path, help="Optionally open a DXF at startup.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("out"),
        help="Default output directory for emit commands (default: out).",
    )
    args = parser.parse_args(argv)

    state = SessionState(output_dir=args.output)
    if args.input is not None:
        state.input_dxf = args.input
    shell = AugradeShell(state)
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
