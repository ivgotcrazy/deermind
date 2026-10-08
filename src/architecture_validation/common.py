from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(dumps(value).encode("utf-8")).hexdigest()


def uid(prefix="r"):
    return prefix + "_" + uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DuplicateJSONKey")
            result[key] = value
        return result
    def constant(_):
        raise ValueError("NonFiniteJSON")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


class Rejected(Exception):
    """A typed boundary failure, never a policy outcome."""


OWNERS = {"Observation": "Interaction", "Decision": "Interaction", "ActionIntent": "Interaction",
          "Evidence": "Evaluation", "Belief": "Evaluation", "EvaluationCompletion": "Evaluation",
          "TaskFamily": "Learning", "TaskInstance": "Learning", "SolutionStrategy": "Learning", "KC": "Learning",
          "Claim": "Evaluation", "EvidenceSemantics": "Evaluation", "InferenceSemantics": "Evaluation",
          "Protocol": "AIRuntime", "ActionSemantics": "Interaction"}
