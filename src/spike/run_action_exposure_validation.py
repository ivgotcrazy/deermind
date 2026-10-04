"""Execute the frozen D1/D2 action and disclosure profile without external model calls."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from foundation.cases import EvidenceRecorder
from foundation.action_cases import CASES
from run_foundation import manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "runs")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    fixture = json.loads((Path(__file__).parent / "fixtures/action-exposure-v1.json").read_text(encoding="utf-8"))
    run_id = "action-exposure-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12]
    directory = args.output / run_id
    directory.mkdir(parents=True, exist_ok=False)
    frozen = manifest(repo)
    frozen.update(cases=fixture["cases"], scope=fixture["scope"], fixture=fixture,
                  assumption_status="ASSESSMENT_PENDING")
    (directory / "manifest.json").write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8")
    results = []
    for name in fixture["cases"]:
        recorder = EvidenceRecorder(directory / f"{name}.jsonl")
        error = None
        try:
            recorder.emit("case_start", case_id=name, profile=fixture)
            CASES[name](recorder)
        except Exception as exc:
            error = {"type": type(exc).__name__, "reason": str(exc)}
            recorder.emit("execution_failure", **error)
        finally:
            result = {"case_id": name, "execution_result": "PASS" if error is None and recorder.checks
                      and all(c["passed"] for c in recorder.checks) else "FAIL",
                      "check_count": len(recorder.checks), "error": error, "assumption_result": None}
            recorder.emit("case_end", **result)
            recorder.close()
        results.append(result)
        print(json.dumps(result), flush=True)
    summary = {"run_id": run_id, "status": "PASS" if all(c["execution_result"] == "PASS" for c in results) else "NON_SUCCESS",
               "cases": results, "model_calls": 0, "assumption_assessment": "PENDING_EVIDENCE_REVIEW",
               "gate_E": "OPEN", "gate_F": "OPEN"}
    (directory / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"directory": str(directory.resolve()), **summary}), flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
