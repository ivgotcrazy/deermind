"""Frozen new samples, repeated review executions, explicit per-batch budget."""

import argparse
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import random
from uuid import uuid4

from foundation.cases import EvidenceRecorder
from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, ModelFailure, load_config
from foundation.records import json_value
from foundation.runtime import ContractError
from foundation.security import AccessDenied
from run_foundation import manifest


ROOT = Path(__file__).resolve().parent


def load_design(filename="observation-stability-v1.json"):
    fixture = json.loads((ROOT / "fixtures" / filename).read_text(encoding="utf-8"))
    content = (ROOT / fixture["protocol_path"]).read_bytes()
    if sha256(content).hexdigest() != fixture["protocol_sha256"]:
        raise ValueError("FrozenProtocolHashMismatch: register a new design instead of changing a frozen protocol")
    return fixture, json.loads(content)


def schedule(fixture):
    rng = random.Random(fixture["schedule_seed"])
    entries = []
    for repetition in range(1, fixture["planned_repetitions"] + 1):
        block = list(fixture["cases"])
        rng.shuffle(block)
        entries.extend((case, repetition) for case in block)
    return entries


def summarize(results, fixture, model_calls):
    positive = sum(c["expected_status"] == "PASS" for c in fixture["cases"]) * fixture["planned_repetitions"]
    negative = fixture["planned_model_calls"] - positive
    counts = {"matched_runs": 0, "false_positives": 0, "false_negatives": 0,
              "unresolved_reviews": 0, "protocol_or_runtime_failures": 0,
              "criterion_or_commit_mismatches": 0}
    for row in results:
        if row["result"] == "PASS":
            counts["matched_runs"] += 1
        if row.get("semantic_status") == "UNRESOLVED":
            counts["unresolved_reviews"] += 1
        if row.get("failure_type"):
            counts["protocol_or_runtime_failures"] += 1
        if row.get("false_positive"):
            counts["false_positives"] += 1
        if row.get("false_negative"):
            counts["false_negatives"] += 1
        if row["result"] == "FAIL" and not row.get("false_positive") and not row.get("false_negative"):
            counts["criterion_or_commit_mismatches"] += 1
    per_case = []
    for case in fixture["cases"]:
        runs = [r for r in results if r["case_id"] == case["id"]]
        signatures = {(r.get("semantic_status", "ERROR"), tuple(sorted(r.get("criterion_statuses", {}).items())),
                       r.get("commit_status"), r.get("failure_type"), r.get("reason")) for r in runs}
        per_case.append({"case_id": case["id"], "expected_status": case["expected_status"],
                         "planned": fixture["planned_repetitions"], "completed": len(runs),
                         "matched": sum(r["result"] == "PASS" for r in runs),
                         "outcomes": dict(Counter(r.get("semantic_status", "ERROR") for r in runs)),
                         "distinct_decision_signatures": len(signatures),
                         "all_expected": len(runs) == fixture["planned_repetitions"] and all(r["result"] == "PASS" for r in runs)})
    return {"status": "PASS" if len(results) == fixture["planned_model_calls"] and all(r["result"] == "PASS" for r in results) else "NON_SUCCESS",
            "planned_runs": fixture["planned_model_calls"], "completed_runs": len(results),
            "not_run": fixture["planned_model_calls"] - len(results), "model_calls": model_calls,
            "positive_runs_planned": positive, "negative_runs_planned": negative, **counts,
            "per_case": per_case, "runs": results, "assumption_status": "UNVALIDATED",
            "scope": fixture["scope"], "measurement_note": "Counts over a designed sample; not an independent population error-rate estimate"}


def write_summary(directory, summary):
    destination = directory / "summary.json"
    temporary = directory / "summary.next.json"
    temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)


def run_suite(config, directory, fixture, protocol, adapter=None, progress=None):
    if config.max_calls < fixture["planned_model_calls"]:
        raise ValueError("Budget below complete preregistered schedule; no calls made")
    adapter = adapter or DeepSeekAdapter(config)
    recorder = EvidenceRecorder(directory / "evidence.jsonl")
    results, written_calls = [], 0
    write_summary(directory, summarize(results, fixture, adapter.calls))
    try:
        recorder.emit("predeclared_design", fixture=fixture, protocol=protocol,
                      schedule=[{"case_id": c["id"], "repetition": n} for c, n in schedule(fixture)],
                      config=config.public())
        for case, repetition in schedule(fixture):
            h, security, runtime, token, context, _, _ = setup_boundary(
                prepare_candidate=False, protocol_payload=protocol, destination=config.base_url,
                work_payload=case["work"])
            candidate = runtime.propose(context, "O", "r1", case["candidate"])
            row = {"case_id": case["id"], "repetition": repetition, "result": "INCONCLUSIVE",
                   "expected_status": case["expected_status"], "expected_criteria": case["expected_criteria"],
                   "expected_commit": case["expected_commit"]}
            recorder.emit("candidate", case_id=case["id"], repetition=repetition,
                          context=json_value(context), candidate=json_value(candidate))
            try:
                review = runtime.validate_with_llm(token, candidate, adapter)
                recorder.emit("semantic_validation", case_id=case["id"], repetition=repetition, value=json_value(review))
                outcome = runtime.commit(token, candidate, review.identity)
                recorder.emit("commit", case_id=case["id"], repetition=repetition, value=json_value(outcome))
                criteria = {r["id"]: r["status"] for r in json.loads(review.details_json)["criteria"]}
                matched = (review.status == case["expected_status"] and outcome.status == case["expected_commit"]
                           and all(criteria.get(k) == v for k, v in case["expected_criteria"].items()))
                row.update(result="PASS" if matched else "INCONCLUSIVE" if review.status == "UNRESOLVED" else "FAIL",
                           semantic_status=review.status, criterion_statuses=criteria, commit_status=outcome.status,
                           false_positive=case["expected_status"] == "FAIL" and review.status == "PASS",
                           false_negative=case["expected_status"] == "PASS" and review.status == "FAIL")
            except (ModelFailure, ContractError, AccessDenied) as exc:
                row.update(failure_type=type(exc).__name__, reason=str(exc))
                recorder.emit("failure", **row)
            finally:
                # Persist each call immediately: later interruptions must not lose earlier evidence.
                for record in adapter.records[written_calls:]:
                    recorder.emit("model_execution", case_id=case["id"], repetition=repetition, **record)
                written_calls = len(adapter.records)
            recorder.capture(h, f"{case['id']}:{repetition}:after")
            recorder.emit("case_result", **row)
            results.append(row)
            summary = summarize(results, fixture, adapter.calls)
            write_summary(directory, summary)
            if progress:
                progress(summary)
    finally:
        recorder.close()
    return summarize(results, fixture, adapter.calls)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--max-calls", type=int, help="Explicit budget override for this batch; does not edit .env")
    parser.add_argument("--max-output-tokens", type=int, help="Explicit per-call output budget; does not edit .env")
    parser.add_argument("--fixture", choices=("observation-stability-v1.json", "observation-grounding-v1.json"),
                        default="observation-stability-v1.json")
    args = parser.parse_args(argv)
    fixture, protocol = load_design(args.fixture)
    repo = ROOT.parents[1]
    configured = load_config(repo)
    config = replace(configured, max_calls=args.max_calls) if args.max_calls is not None else configured
    if args.max_output_tokens is not None:
        config = replace(config, max_output_tokens=args.max_output_tokens)
    if not args.run:
        print(json.dumps({"planned_calls": fixture["planned_model_calls"], "effective_config": config.public(),
                          "configured_max_calls": configured.max_calls,
                          "ready": bool(config.api_key) and config.max_calls >= fixture["planned_model_calls"],
                          "protocol_sha256": fixture["protocol_sha256"], "network_calls": 0}, indent=2))
        return 0
    if not config.api_key or config.max_calls < fixture["planned_model_calls"]:
        print(json.dumps({"status": "NEEDS_CONFIG", "reason": "Key and an explicit budget covering all planned calls are required"}))
        return 2
    directory = ROOT / "runs" / ("semantic-stability-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12])
    directory.mkdir(parents=True, exist_ok=False)
    run_manifest = manifest(repo)
    run_manifest.update(scope=fixture["scope"], fixture=fixture, model_config=config.public(),
                        configured_max_calls=configured.max_calls, explicit_max_calls_override=args.max_calls,
                        configured_max_output_tokens=configured.max_output_tokens,
                        explicit_max_output_tokens_override=args.max_output_tokens,
                        cases=[c["id"] for c in fixture["cases"]], repetitions=fixture["planned_repetitions"],
                        planned_calls=fixture["planned_model_calls"], model_calls="see summary.json")
    (directory / "manifest.json").write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(directory.resolve()), "planned_calls": fixture["planned_model_calls"]}), flush=True)
    def progress(summary):
        if summary["completed_runs"] % len(fixture["cases"]) == 0:
            print(json.dumps({key: summary[key] for key in ("completed_runs", "matched_runs", "false_positives", "false_negatives", "protocol_or_runtime_failures")}), flush=True)
    summary = run_suite(config, directory, fixture, protocol, progress=progress)
    print(json.dumps({k: v for k, v in summary.items() if k != "runs"}, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
