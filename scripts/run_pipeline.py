from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_import_path(root: Path) -> None:
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"{label} not found: {path}. "
            "Run this command from a complete clone of the repository."
        )


def run_finalize(root: Path) -> dict[str, str]:
    _ensure_import_path(root)
    from empriority.finalize_dataset_v2 import finalize_dataset_v2

    matrix = root / "data" / "processed" / "integrated_municipal_matrix.csv"
    output = root / "data" / "processed"
    _require_file(matrix, "Integrated municipal matrix")

    outputs = finalize_dataset_v2(matrix_path=matrix, output_directory=output)
    return {name: str(path.relative_to(root)) for name, path in outputs.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run reproducible project pipeline stages locally or in GitHub Actions."
        )
    )
    parser.add_argument(
        "--stage",
        choices=("finalize",),
        default="finalize",
        help="Pipeline stage to execute (default: finalize).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = _project_root()

    try:
        if args.stage == "finalize":
            outputs = run_finalize(root)
        else:  # pragma: no cover - argparse prevents this path
            raise ValueError(f"Unsupported stage: {args.stage}")
    except Exception as exc:
        print(f"PIPELINE FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("PIPELINE COMPLETED")
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
