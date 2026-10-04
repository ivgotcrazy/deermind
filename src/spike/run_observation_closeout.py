"""One bounded S1/S2 campaign: frozen inputs, no replacement runs or hidden retries."""

import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from foundation.llm import load_config
from run_foundation import manifest
from run_semantic_stability import ROOT, load_design, run_suite, write_summary


def s2_eligible(summary):
    return summary["not_run"] == 0 and not summary.get("stop_reason") and not summary.get("forbidden_commits")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    plans = [load_design(f"observation-closeout-{batch}-v1.json") for batch in ("s1", "s2")]
    assert plans[0][1] == plans[1][1]
    repo = ROOT.parents[1]
    configured = load_config(repo)
    config = replace(configured, base_url="https://api.deepseek.com/beta", max_output_tokens=3072, timeout_seconds=60)
    directory = ROOT / "runs" / "observation-closeout-v1"
    ready = bool(config.api_key) and not directory.exists()
    if not args.run:
        print(json.dumps({"ready": ready, "already_reserved": directory.exists(), "network_calls": 0,
                          "effective_model": config.public(), "candidate_executions": [120, 60],
                          "batch_call_limits": [480, 240], "total_limit": 720,
                          "protocol_sha256": plans[0][0]["protocol_sha256"]}, indent=2))
        return 0 if ready else 2
    if not ready:
        print(json.dumps({"status": "NOT_STARTED", "reason": "Missing key or campaign already reserved; no automatic rerun."}))
        return 2
    directory.mkdir(parents=True, exist_ok=False)
    frozen = manifest(repo)
    frozen.update(scope="Bounded S1/S2 closeout; exactly one reservation, no automatic resume after interruption.",
                  model_config=config.public(), batches=[f for f, _ in plans], total_model_call_limit=720,
                  assumption_status="ASSESSMENT_PENDING")
    (directory / "manifest.json").write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8")
    outcomes = []
    for fixture, protocol in plans:
        if outcomes and not s2_eligible(outcomes[0]["summary"]):
            outcomes.append({"batch": "S2", "status": "NOT_RUN", "reason": "S1 stop condition; no replacement batch."})
            break
        changed = [p for p, h in frozen["content_sha256"].items() if sha256((repo / p).read_bytes()).hexdigest() != h]
        if changed:
            outcomes.append({"batch": fixture["batch"], "status": "NOT_RUN", "reason": "FrozenInputsChanged", "paths": changed})
            break
        batch_dir = directory / fixture["batch"]
        batch_dir.mkdir(exist_ok=False)
        batch_config = replace(config, max_calls=fixture["max_model_calls"])
        batch_manifest = dict(frozen, fixture=fixture, model_config=batch_config.public(),
                              cases=[c["id"] for c in fixture["cases"]], repetitions=5)
        (batch_dir / "manifest.json").write_text(json.dumps(batch_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"batch": fixture["batch"], "output": str(batch_dir), "planned_candidates": fixture["planned_model_calls"]}), flush=True)
        def progress(summary):
            if summary["completed_runs"] % 6 == 0 or summary.get("stop_reason"):
                print(json.dumps({"batch": fixture["batch"], **{k: summary[k] for k in (
                    "completed_runs", "matched_runs", "composite_outcome_matches", "forbidden_commits", "protocol_or_runtime_failures", "stop_reason")}}), flush=True)
        summary = run_suite(batch_config, batch_dir, fixture, protocol, progress=progress)
        outcomes.append({"batch": fixture["batch"], "summary": summary})
        write_summary(directory, {"status": "IN_PROGRESS", "batches": outcomes})
    final = {"status": "EXECUTION_FINISHED_ASSESSMENT_PENDING", "batches": outcomes,
             "model_calls": sum(b.get("summary", {}).get("model_calls", 0) for b in outcomes),
             "maximum_model_calls": 720, "automatic_additional_batches": False,
             "original_AA_A02": "DENIED", "gate_E": "OPEN", "gate_F": "OPEN"}
    write_summary(directory, final)
    print(json.dumps({k: v for k, v in final.items() if k != "batches"}), flush=True)
    return 0 if len(outcomes) == 2 and all(b.get("summary", {}).get("status") == "PASS" for b in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
