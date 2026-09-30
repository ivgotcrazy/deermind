"""Run deterministic foundation cases and retain evidence in a new run directory."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from foundation.cases import CASES, run_case


def manifest(repo):
    paths = sorted(set(repo.joinpath("doc").rglob("*.md"))
                   | set(repo.joinpath("src", "spike").rglob("*.py"))
                   | {repo / "src" / "spike" / "README.md", repo / ".gitignore"})
    hashes = {p.relative_to(repo).as_posix(): sha256(p.read_bytes()).hexdigest() for p in paths}
    def git(*args):
        result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    return {"schema": "foundation-run-v1", "created_at": datetime.now(timezone.utc).isoformat(),
            "git_head": git("rev-parse", "HEAD"), "git_status": git("status", "--short"),
            "content_sha256": hashes, "python": sys.version, "cases": list(CASES),
            "repetitions": 1, "model_calls": 0, "model_config": None,
            "scope": "Step 0–2 deterministic foundation; scripted owner records and eligibility",
            "assumption_status": "UNVALIDATED", "gate_E": "OPEN", "gate_F": "OPEN",
            "hidden_complexity": [
                {"mechanism": "deep-copy snapshot per current resolution",
                 "reason": "one consistent in-memory read basis",
                 "correctness_dependency": "consistent view required; deepcopy is replaceable",
                 "limitation": "no production performance or concurrency claim"}]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "runs")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    run_manifest = manifest(repo)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12]
    directory = args.output / run_id
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "manifest.json").write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    results = [run_case(name, case, directory) for name, case in CASES.items()]
    summary = {"run_id": run_id, "cases": results, "assumption_status": "UNVALIDATED",
               "limitations": ["No FormalCommit, authority backend, real LLM or replay implementation",
                               "Foundation PASS is not architecture assumption SUPPORTED"]}
    (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(directory.resolve()), **summary}, ensure_ascii=False, indent=2))
    return 0 if all(r["foundation_result"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
