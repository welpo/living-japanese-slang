from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from .build import run


def parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[2]
    result = argparse.ArgumentParser(description="Build the Living Japanese Slang Yomitan dictionary")
    result.add_argument("--date", default=datetime.now().date().isoformat(), help="Build date (YYYY-MM-DD)")
    result.add_argument(
        "--offline", action="store_true", help="Rebuild an existing dated snapshot without network access"
    )
    result.add_argument("--output", type=Path, default=root / "dist")
    result.add_argument("--baseline", type=Path, default=root / "data/current-entries.json")
    result.add_argument("--state", type=Path, default=root / "data/state.json")
    result.add_argument("--overrides", type=Path, default=root / "overrides.toml")
    return result


def main(argv: Sequence[str] | None = None) -> None:
    arguments = parser().parse_args(argv)
    build_date = datetime.strptime(arguments.date, "%Y-%m-%d").date().isoformat()
    root = Path(__file__).resolve().parents[2]
    summary = run(
        root=root,
        output=arguments.output.resolve(),
        build_date=build_date,
        offline=arguments.offline,
        baseline_path=arguments.baseline.resolve(),
        state_path=arguments.state.resolve(),
        overrides_path=arguments.overrides.resolve(),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
