"""从 FastAPI 和公开内容模型导出合同，不连接集群或数据库。"""

import argparse
import json
from pathlib import Path

from deermind.entrypoints.api.app import create_app
from deermind.spaces.domain.public import RichContent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if a saved schema differs")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "contracts/generated"
    contracts = {
        "http/openapi.json": create_app().openapi(),
        "content/rich-content.schema.json": RichContent.model_json_schema(),
    }
    for name, contract in contracts.items():
        path = root / name
        schema = json.dumps(contract, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != schema:
                raise SystemExit(f"Generated contract differs: {name}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(schema, encoding="utf-8")


if __name__ == "__main__":
    main()
