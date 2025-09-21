"""Layout schema migration helper stub."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Dict, Mapping, Tuple


Migrator = Callable[[Mapping[str, object]], Mapping[str, object]]


MIGRATORS: Dict[Tuple[str, str], Migrator] = {}


def _prepare_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate layout JSON between schema versions")
    parser.add_argument("--in", dest="input_path", required=True, type=Path, help="Source layout JSON path")
    parser.add_argument("--out", dest="output_path", required=True, type=Path, help="Destination path")
    parser.add_argument("--from", dest="version_from", required=True, help="Source schema version")
    parser.add_argument("--to", dest="version_to", required=True, help="Target schema version")
    return parser


def _load_layout(path: Path) -> Mapping[str, object]:
    with path.expanduser().open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_layout(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def _copy_bytes(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes())


def main(argv: list[str] | None = None) -> int:
    parser = _prepare_parser()
    args = parser.parse_args(argv)

    src = args.input_path
    dest = args.output_path
    version_from = args.version_from
    version_to = args.version_to

    if version_from == version_to:
        try:
            _copy_bytes(src, dest)
        except FileNotFoundError:
            parser.error(f"Input file not found: {src}")
        return 0

    migrator = MIGRATORS.get((version_from, version_to))
    if migrator is None:
        print(
            f"Unsupported migration path: {version_from} -> {version_to}",
            file=sys.stderr,
        )
        return 2

    payload = _load_layout(src)
    updated = migrator(payload)
    _write_layout(dest, updated)
    return 0


if __name__ == "__main__":
    sys.exit(main())

