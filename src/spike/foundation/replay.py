"""Exact historical reconstruction and explicitly new re-execution for the Spike.

Raw artifact retention and provider availability are controlled experiment fixtures.
No inference from natural-language content occurs here.
"""

from hashlib import sha256

from .records import Ref, Space, json_value
from .runtime import ContractError
from .security import AccessDenied, DataUse, Operation


def exact(value):
    return Ref(Space(value["space"]), value["identity"], value["revision"])


class ArtifactStore:
    """External bytes fixture. Tombstones do not recreate or change historical facts."""
    def __init__(self):
        self._values, self.removals = {}, {}

    def put_fixture(self, ref, content):
        if ref in self._values or ref in self.removals:
            raise ContractError("ArtifactIdentityImmutable")
        self._values[ref] = content

    def remove_fixture(self, ref, reason):
        if ref not in self._values or not reason:
            raise ContractError("MissingArtifactOrRemovalReason")
        del self._values[ref]
        self.removals[ref] = reason

    def load(self, record):
        content = self._values.get(record.ref)
        if content is None:
            return None, "RawArtifactRemoved" if record.ref in self.removals else "RawArtifactMissing"
        if sha256(content.encode("utf-8")).hexdigest() != record.payload["sha256"]:
            return None, "RawArtifactDigestMismatch"
        return content, None


class ReplayRuntime:
    def __init__(self, boundary, artifacts, models, *, subject="learner-A", purpose="learning"):
        self.boundary = boundary
        self.h, self.security = boundary.h, boundary.security
        self.artifacts, self.models = artifacts, models
        self.subject, self.purpose = subject, purpose

    def _load(self, token, root, operation, source):
        # Authorize the requested identity even when its retained record is missing.
        self.security.enforce(token, Operation(self.purpose, self.subject, root.identity, operation), source,
                              DataUse(self.purpose, self.subject, "ReplayManifest", operation, "replay-runtime"))
        if self.h.get(root) is None:
            return None, {}, {}, ["HistoricalManifestMissing"]
        record, _ = self.security.read(token, root, self.purpose, "replay-runtime", source, ("ReplayManifest",))
        manifest = record.payload
        records, raw, gaps = {}, {}, []
        for name, value in manifest["records"].items():
            ref = exact(value)
            # Missing retained history is a capability gap, not permission to synthesize it.
            if self.h.get(ref) is None:
                self.security.enforce(token, Operation(self.purpose, self.subject, ref.identity, "read"), source)
                gaps.append(f"HistoricalRecordMissing:{name}")
                continue
            item, _ = self.security.read(token, ref, self.purpose, "replay-runtime", source)
            records[name] = json_value(item)
            if item.kind == "GroundingArtifact":
                content, reason = self.artifacts.load(item)
                if reason:
                    gaps.append(reason)
                else:
                    raw[name] = content
        return manifest, records, raw, gaps

    def _result(self, operation, root, capability, reasons, *, view=None, generated=None, extra=None):
        payload = {"operation": operation, "source_execution": json_value(root),
                   "capability": capability, "reasons": reasons, **(extra or {})}
        if generated is not None:
            payload["generated_output"] = generated
            payload["standing"] = "EXECUTION_ONLY_NOT_HISTORICAL_OUTPUT"
            payload["validation"] = "NOT_PERFORMED_NO_FORMAL_COMMIT"
        execution = self.boundary.execution("ReplayOperationExecution", self.subject, payload)
        return {"operation": operation, "capability": capability, "reasons": reasons,
                "historical_view": view, "generated_output": generated, "execution": json_value(execution)}

    def historical_reconstruct(self, token, root):
        operation = "historical_reconstruct"
        source = self.boundary.execution("ReplayRequested", self.subject, {"operation": operation, "root": json_value(root)})
        self.h.control.reach("beforeReplay")
        try:
            manifest, records, raw, gaps = self._load(token, root, operation, source)
        except AccessDenied as exc:
            return self._result(operation, root, "UNAVAILABLE", [exc.category])
        if manifest is None or "output" not in records:
            return self._result(operation, root, "UNAVAILABLE", gaps or ["HistoricalOutputMissing"])
        view = {"records": records, "raw_artifacts": raw, "recorded_model": manifest["model_ref"],
                "version_context": records["output"]["versions"], "historical_output": records["output"]["payload_json"]}
        return self._result(operation, root, "PARTIAL" if gaps else "FULL", gaps, view=view)

    def reexecute(self, token, root, requested_environment):
        operation = "reexecute"
        source = self.boundary.execution("ReplayRequested", self.subject,
                                         {"operation": operation, "root": json_value(root), "requested_environment": requested_environment})
        self.h.control.reach("beforeReplay")
        try:
            manifest, records, raw, gaps = self._load(token, root, operation, source)
        except AccessDenied as exc:
            return self._result(operation, root, "UNAVAILABLE", [exc.category])
        if manifest is None or gaps:
            return self._result(operation, root, "UNAVAILABLE", gaps)
        model = self.models.get(requested_environment)
        if model is None:
            return self._result(operation, root, "UNAVAILABLE", ["RequestedModelRevisionUnavailable"])
        # The explicit environment may be different; never silently substitute a provider.
        differing = requested_environment != manifest["model_ref"]
        try:
            output = model(raw, records)
            # A callback may have invalidated permission; no resulting content is returned then.
            _, _, _, late_gaps = self._load(token, root, operation, source)
            if late_gaps:
                return self._result(operation, root, "UNAVAILABLE", late_gaps)
        except AccessDenied as exc:
            return self._result(operation, root, "UNAVAILABLE", [exc.category])
        except Exception as exc:
            return self._result(operation, root, "UNAVAILABLE", [f"ReexecutionFailed:{type(exc).__name__}"])
        return self._result(operation, root, "PARTIAL" if differing else "FULL",
                            ["RequestedEnvironmentDiffersFromHistorical"] if differing else [], generated=output,
                            extra={"requested_historical_model": manifest["model_ref"],
                                   "actually_resolved_environment": requested_environment,
                                   "requested_historical_version_context": records["output"]["versions"],
                                   "fidelity_note": "FULL describes available inputs/environment, not identical output."})
