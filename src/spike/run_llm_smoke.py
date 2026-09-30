"""Preflight by default; --run performs one real generation and one real review."""

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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Make real API calls within the configured budget")
    parser.add_argument("--check-config", action="store_true", help="Check local configuration without network calls")
    parser.add_argument("--protocol-version", choices=("v1", "v2"), default="v2")
    args = parser.parse_args(argv)
    if args.run and args.check_config:
        parser.error("Use --run or --check-config, not both")
    repo = Path(__file__).resolve().parents[2]
    try:
        config = load_config(repo)
    except ValueError as exc:
        print(json.dumps({"status": "INVALID_CONFIG", "reason": str(exc)}))
        return 2
    if not args.run:
        print(json.dumps({"status": "READY" if config.api_key and config.max_calls >= 2 else "NEEDS_CONFIG",
                          "config": config.public(), "required_calls": 2, "network_calls": 0}, indent=2))
        return 0
    if not config.api_key or config.max_calls < 2:
        print(json.dumps({"status": "NEEDS_CONFIG", "reason": "Set DEERMIND_LLM_API_KEY and a call budget of at least 2"}))
        return 2
    directory = Path(__file__).parent / "runs" / ("llm-smoke-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12])
    directory.mkdir(parents=True, exist_ok=False)
    run_manifest = manifest(repo)
    run_manifest.update(scope="Step 5 two-call smoke only", cases=[f"ObservationSmoke-{args.protocol_version}"],
                        model_config=config.public(), model_calls="see summary.json")
    (directory / "manifest.json").write_text(json.dumps(run_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    protocol = json.loads((Path(__file__).parent / "protocols" / f"observation-smoke-{args.protocol_version}.json").read_text(encoding="utf-8"))
    h, security, runtime, token, context, _, _ = setup_boundary(
        prepare_candidate=False, protocol_payload=protocol, destination=config.base_url)
    recorder = EvidenceRecorder(directory / "evidence.jsonl")
    adapter = DeepSeekAdapter(config)
    summary = {"status": "FAILED", "assumption_status": "UNVALIDATED", "model_calls": 0}
    try:
        recorder.capture(h, "before-model")
        recorder.emit("context", package=json_value(context), grants=security.describe_grants())
        candidate = runtime.generate_with_llm(token, context, adapter)
        recorder.emit("candidate", value=json_value(candidate))
        review = runtime.validate_with_llm(token, candidate, adapter)
        recorder.emit("semantic_validation", value=json_value(review))
        outcome = runtime.commit(token, candidate, review.identity)
        recorder.emit("commit", value=json_value(outcome))
        summary.update(status="PASS" if outcome.status == "Committed" else "NON_SUCCESS",
                       commit_status=outcome.status, semantic_status=review.status)
    except (ModelFailure, ContractError, AccessDenied) as exc:
        summary["failure"] = str(exc)
        recorder.emit("failure", category=type(exc).__name__, reason=str(exc))
    finally:
        for record in adapter.records:
            recorder.emit("model_execution", **record)
        recorder.capture(h, "after-model")
        recorder.close()
        summary["model_calls"] = adapter.calls
        (directory / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(directory.resolve()), **summary}, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
