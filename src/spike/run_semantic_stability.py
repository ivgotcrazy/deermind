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
from foundation.claim_axes import assess_expected_axes
from foundation.responsibility import assess_expected_roles
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
    case_by_id = {c["id"]: c for c in fixture["cases"]}
    def expected(row, key):
        return row.get(key, case_by_id.get(row.get("case_id"), {}).get(key))
    outcome_matches = sum(expected(r, "expected_status") in ("PASS", "FAIL")
                          and r.get("semantic_status") == expected(r, "expected_status")
                          and r.get("commit_status") in ("Committed", "ValidationFailed")
                          and r.get("commit_status") == expected(r, "expected_commit") and not r.get("failure_type") for r in results)
    stop_reason = None
    if results:
        last = results[-1]
        if fixture.get("stop_on_false_commit") and expected(last, "expected_status") == "FAIL" and last.get("commit_status") == "Committed":
            stop_reason = "ForbiddenCommitObserved"
        elif last.get("reason") in fixture.get("stop_on_provider_failures", []):
            stop_reason = last["reason"]
        else:
            limit = fixture.get("stop_after_consecutive_protocol_failures", 0)
            if limit and len(results) >= limit and all(r.get("failure_type") for r in results[-limit:]):
                stop_reason = "ConsecutiveProtocolOrRuntimeFailures"
    return {"status": "PASS" if len(results) == fixture["planned_model_calls"] and all(r["result"] == "PASS" for r in results) else "NON_SUCCESS",
            "composite_outcome_matches": outcome_matches,
            "composite_status": "PASS" if len(results) == fixture["planned_model_calls"] == outcome_matches else "NON_SUCCESS",
            "forbidden_commits": sum(expected(r, "expected_status") == "FAIL" and r.get("commit_status") == "Committed" for r in results),
            "stop_reason": stop_reason,
            "planned_runs": fixture["planned_model_calls"], "completed_runs": len(results),
            "not_run": fixture["planned_model_calls"] - len(results), "model_calls": model_calls,
            "positive_runs_planned": positive, "negative_runs_planned": negative, **counts,
            "per_case": per_case, "runs": results, "assumption_status": "UNVALIDATED",
            "initial_source_conflicts": sum(r.get("initial_source_conflict", False) for r in results),
            "recheck_calls": sum(r.get("recheck_calls", 0) for r in results),
            "recheck_failures": sum(r.get("recheck_failed", False) for r in results),
            "max_model_calls": fixture.get("max_model_calls", fixture["planned_model_calls"]),
            "extraction_calls": sum(r.get("extraction_calls", 0) for r in results),
            "arithmetic_overrides": sum(r.get("llm_semantic_status") == "PASS" and r.get("arithmetic_status") == "FAIL"
                                        and r.get("effective_status") == "FAIL" for r in results),
            "claim_axis_mismatches": sum(any(not a["matches"] for a in r.get("claim_axes", [])) for r in results),
            "responsibility_calls": sum(r.get("responsibility_calls", 0) for r in results),
            "responsibility_role_mismatches": sum(any(not a["matches"] for a in r.get("responsibility_roles", [])) for r in results),
            "responsibility_overrides": sum(r.get("pre_responsibility_status") == "PASS" and r.get("responsibility_status") == "FAIL"
                                            and r.get("effective_status") == "FAIL" for r in results),
            "scope": fixture["scope"], "measurement_note": "Counts over a designed sample; not an independent population error-rate estimate"}


def write_summary(directory, summary):
    destination = directory / "summary.json"
    temporary = directory / "summary.next.json"
    temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)


def run_suite(config, directory, fixture, protocol, adapter=None, progress=None):
    if protocol.get("provider_endpoint", config.base_url) != config.base_url:
        raise ValueError("ProtocolProviderEndpointMismatch: use the explicitly declared endpoint")
    if config.max_calls < fixture.get("max_model_calls", fixture["planned_model_calls"]):
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
                execution = h.get(review.execution).payload
                arithmetic_status = (execution.get("arithmetic_result") or {}).get("status")
                axes = assess_expected_axes(json.loads(review.details_json), case["candidate"], case.get("expected_claim_axes", []))
                if axes:
                    row["claim_axes"] = axes
                matched = (review.status == case["expected_status"] and outcome.status == case["expected_commit"]
                           and all(criteria.get(k) == v for k, v in case["expected_criteria"].items())
                           and all(a["matches"] for a in axes)
                           and ("expected_arithmetic_status" not in case or arithmetic_status == case["expected_arithmetic_status"]))
                row.update(result="PASS" if matched else "INCONCLUSIVE" if review.status == "UNRESOLVED" else "FAIL",
                           semantic_status=review.status, criterion_statuses=criteria, commit_status=outcome.status,
                           false_positive=case["expected_status"] == "FAIL" and review.status == "PASS",
                           false_negative=case["expected_status"] == "PASS" and review.status == "FAIL")
                if arithmetic_status is not None:
                    row.update(arithmetic_status=arithmetic_status, llm_semantic_status=execution["semantic_status"],
                               effective_status=review.status)
                if execution.get("responsibility_result") is not None:
                    row["pre_responsibility_status"] = execution["pre_responsibility_status"]
            except (ModelFailure, ContractError, AccessDenied) as exc:
                row.update(failure_type=type(exc).__name__, reason=str(exc))
                recorder.emit("failure", **row)
            finally:
                classified = [r for r in h.executions.records() if r.kind == "ResponsibilityClassificationExecution"]
                if classified:
                    result = classified[-1].payload["result"]
                    roles = assess_expected_roles(result, case["candidate"], case.get("expected_responsibility_roles", []))
                    row.update(responsibility_status=result["status"], responsibility_roles=roles)
                    if row["result"] == "PASS" and (not all(r["matches"] for r in roles)
                            or result["status"] != case.get("expected_responsibility_status", result["status"])):
                        row["result"] = "FAIL"
                    recorder.emit("responsibility_classification", case_id=case["id"], repetition=repetition,
                                  execution=classified[-1].payload)
                history = runtime.validation_history(candidate)
                for attempt in history:
                    recorder.emit("validation_attempt", case_id=case["id"], repetition=repetition,
                                  value=json_value(attempt), execution=h.get(attempt.execution).payload)
                row.update(initial_source_conflict=bool(history and h.get(history[0].execution).payload.get("source_conflicts")),
                           initial_semantic_status=history[0].status if history else None,
                           recheck_calls=sum(r["purpose"] == "ObservationSemanticRecheck" for r in adapter.records[written_calls:]),
                           extraction_calls=sum(r["purpose"] == "ArithmeticExtraction" for r in adapter.records[written_calls:]),
                           responsibility_calls=sum(r["purpose"] == "ObservationResponsibilityClassification" for r in adapter.records[written_calls:]),
                           recheck_failed=any(r.kind == "SemanticRecheckFailed" for r in h.executions.records()))
                # Persist all calls from this candidate, including failed stages.
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
            if summary.get("stop_reason"):
                recorder.emit("batch_stopped", reason=summary["stop_reason"], not_run=summary["not_run"])
                break
    finally:
        recorder.close()
    return summarize(results, fixture, adapter.calls)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--max-calls", type=int, help="Explicit budget override for this batch; does not edit .env")
    parser.add_argument("--max-output-tokens", type=int, help="Explicit per-call output budget; does not edit .env")
    parser.add_argument("--base-url", help="Explicit endpoint for this batch; does not edit .env")
    parser.add_argument("--fixture", choices=("observation-stability-v1.json", "observation-grounding-v1.json",
                                              "observation-absence-v1.json", "observation-support-v1.json",
                                              "observation-arithmetic-v1.json", "observation-structured-v1.json",
                                              "observation-support-structured-v1.json", "observation-source-handles-v1.json",
                                              "observation-claim-axes-v1.json", "observation-responsibility-v1.json",
                                              "observation-closeout-s1-v1.json", "observation-closeout-s2-v1.json"),
                        default="observation-stability-v1.json")
    args = parser.parse_args(argv)
    fixture, protocol = load_design(args.fixture)
    maximum_calls = fixture.get("max_model_calls", fixture["planned_model_calls"])
    repo = ROOT.parents[1]
    configured = load_config(repo)
    config = replace(configured, max_calls=args.max_calls) if args.max_calls is not None else configured
    if args.max_output_tokens is not None:
        config = replace(config, max_output_tokens=args.max_output_tokens)
    if args.base_url is not None:
        config = replace(config, base_url=args.base_url.rstrip("/"))
    endpoint_matches = protocol.get("provider_endpoint", config.base_url) == config.base_url
    if not args.run:
        print(json.dumps({"planned_executions": fixture["planned_model_calls"],
                          "planned_calls": fixture.get("initial_model_calls", fixture["planned_model_calls"]), "effective_config": config.public(),
                          "configured_max_calls": configured.max_calls,
                          "max_model_calls": maximum_calls,
                          "ready": bool(config.api_key) and config.max_calls >= maximum_calls and endpoint_matches,
                          "endpoint_matches_protocol": endpoint_matches,
                          "protocol_sha256": fixture["protocol_sha256"], "network_calls": 0}, indent=2))
        return 0
    if not config.api_key or config.max_calls < maximum_calls or not endpoint_matches:
        print(json.dumps({"status": "NEEDS_CONFIG", "reason": "Key, sufficient budget and matching protocol endpoint are required"}))
        return 2
    directory = ROOT / "runs" / ("semantic-stability-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12])
    directory.mkdir(parents=True, exist_ok=False)
    run_manifest = manifest(repo)
    run_manifest.update(scope=fixture["scope"], fixture=fixture, model_config=config.public(),
                        configured_max_calls=configured.max_calls, explicit_max_calls_override=args.max_calls,
                        configured_max_output_tokens=configured.max_output_tokens,
                        explicit_base_url_override=args.base_url,
                        explicit_max_output_tokens_override=args.max_output_tokens,
                        cases=[c["id"] for c in fixture["cases"]], repetitions=fixture["planned_repetitions"],
                        planned_executions=fixture["planned_model_calls"],
                        planned_calls=fixture.get("initial_model_calls", fixture["planned_model_calls"]),
                        max_model_calls=maximum_calls, model_calls="see summary.json")
    (directory / "manifest.json").write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(directory.resolve()), "planned_executions": fixture["planned_model_calls"],
                      "planned_calls": fixture.get("initial_model_calls", fixture["planned_model_calls"])}), flush=True)
    def progress(summary):
        if summary["completed_runs"] % len(fixture["cases"]) == 0:
            print(json.dumps({key: summary[key] for key in ("completed_runs", "matched_runs", "false_positives", "false_negatives", "protocol_or_runtime_failures")}), flush=True)
    summary = run_suite(config, directory, fixture, protocol, progress=progress)
    print(json.dumps({k: v for k, v in summary.items() if k != "runs"}, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
