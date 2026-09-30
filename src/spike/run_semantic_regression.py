"""Two predeclared review calls: original omission and minimally repaired positive."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from foundation.cases import EvidenceRecorder
from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, ModelFailure, load_config
from foundation.records import json_value
from foundation.runtime import ContractError
from foundation.security import AccessDenied
from run_foundation import manifest


def run_pair(config, directory, adapter=None):
    root = Path(__file__).resolve().parent
    protocol = json.loads((root / "protocols/observation-smoke-v2.json").read_text(encoding="utf-8"))
    fixture = json.loads((root / "fixtures/observation-omission-v1.json").read_text(encoding="utf-8"))
    if config.max_calls < fixture["planned_model_calls"]:
        raise ValueError("A two-call budget is required for the declared pair")
    adapter = adapter or DeepSeekAdapter(config)
    recorder = EvidenceRecorder(directory / "evidence.jsonl")
    results = []
    try:
        recorder.emit("predeclared_design", protocol=protocol, fixture=fixture,
                      config=config.public(), assumption_status="UNVALIDATED")
        for case in fixture["cases"]:
            h, security, runtime, token, context, _, _ = setup_boundary(
                prepare_candidate=False, protocol_payload=protocol, destination=config.base_url)
            candidate = runtime.propose(context, "O", "r1", case["candidate"])
            result = {"case_id": case["id"], "regression_result": "INCONCLUSIVE",
                      "expected_status": case["expected_status"], "expected_criteria": case["expected_criteria"],
                      "expected_commit": case["expected_commit"]}
            recorder.emit("candidate", case_id=case["id"], value=json_value(candidate))
            recorder.capture(h, case["id"] + ":before")
            try:
                review = runtime.validate_with_llm(token, candidate, adapter)
                recorder.emit("semantic_validation", case_id=case["id"], value=json_value(review))
                outcome = runtime.commit(token, candidate, review.identity)
                recorder.emit("commit", case_id=case["id"], value=json_value(outcome))
                criteria = {row["id"]: row["status"] for row in json.loads(review.details_json)["criteria"]}
                matched = (review.status == case["expected_status"] and outcome.status == case["expected_commit"]
                           and all(criteria.get(k) == v for k, v in case["expected_criteria"].items()))
                result.update(regression_result="PASS" if matched else "FAIL", semantic_status=review.status,
                              criterion_statuses=criteria, commit_status=outcome.status,
                              false_positive=case["expected_status"] == "FAIL" and review.status == "PASS",
                              false_negative=case["expected_status"] == "PASS" and review.status == "FAIL")
            except (ModelFailure, ContractError, AccessDenied) as exc:
                result.update(failure_type=type(exc).__name__, reason=str(exc))
                recorder.emit("failure", **result)
            recorder.capture(h, case["id"] + ":after")
            recorder.emit("case_result", **result)
            results.append(result)
    finally:
        for record in adapter.records:
            recorder.emit("model_execution", **record)
        recorder.close()
    status = "PASS" if len(results) == 2 and all(r["regression_result"] == "PASS" for r in results) else "NON_SUCCESS"
    return {"status": status, "model_calls": adapter.calls, "cases": results,
            "assumption_status": "UNVALIDATED", "scope": "One predeclared pair; not a reliability estimate"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    config = load_config(repo)
    if not args.run:
        print(json.dumps({"config": config.public(), "planned_calls": 2, "network_calls": 0,
                          "cases": ["original_omission", "repaired_positive"]}, indent=2))
        return 0
    if not config.api_key or config.max_calls < 2:
        print(json.dumps({"status": "NEEDS_CONFIG", "reason": "API key and at least two calls required"}))
        return 2
    directory = Path(__file__).parent / "runs" / ("semantic-regression-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12])
    directory.mkdir(parents=True, exist_ok=False)
    run_manifest = manifest(repo)
    run_manifest.update(scope="Targeted semantic omission regression", cases=["original_omission", "repaired_positive"],
                        model_config=config.public(), model_calls="see summary.json", planned_calls=2,
                        protocol_ref="ObservationSmokeProtocol:v2", rule_ref="ObservationRules:v2",
                        fixture_ref="ObservationOmissionRegression:v1")
    (directory / "manifest.json").write_text(json.dumps(run_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = run_pair(config, directory)
    (directory / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(directory.resolve()), **summary}, indent=2, ensure_ascii=False))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
