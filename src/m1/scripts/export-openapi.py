"""Export implemented HTTP routes from FastAPI; never connect or migrate at export time."""

import argparse
import json
from pathlib import Path

from deermind.entrypoints.api.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the saved schema differs")
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / "contracts/generated/http/openapi.json"
    schema = json.dumps(create_app().openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != schema:
            raise SystemExit("OpenAPI snapshot is missing or differs; regenerate it explicitly")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(schema, encoding="utf-8")


if __name__ == "__main__":
    main()
