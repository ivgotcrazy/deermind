import tempfile
import unittest
from pathlib import Path

from foundation.cases import EvidenceRecorder
from foundation.records import Ref, Space
from foundation.runtime import ContractError
from foundation.version_replay_cases import VersionReplayWorld


class VersionReplayTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.e = EvidenceRecorder(Path(directory.name) / "events.jsonl")
        self.addCleanup(self.e.close)
        self.w = VersionReplayWorld(self.e)
        self.output, self.root = self.w.reinterpret((self.w.work,), self.w.old_protocol.ref, "r1")
        self.token = self.w.tokens["interaction"]

    def test_version_commit_cannot_activate_and_history_remains_exact(self):
        w = self.w
        v2 = w.install_v2()
        with self.assertRaises(ContractError):
            w.reinterpret((w.work,), v2, "r2")
        w.activate(v2)
        new, root = w.reinterpret((w.work,), v2, "r2")
        old_view = w.replay.historical_reconstruct(self.token, self.root)
        self.assertEqual(old_view["historical_view"]["version_context"]["semantic_bindings"][0]["revision"], "v1")
        self.assertEqual(w.h.get(new).versions.semantic_bindings[0], v2)
        self.assertEqual(w.calls, 0)

    def test_current_authority_and_data_authority_required_before_output(self):
        w = self.w
        w.security.revoke("C-replay-"+self.root.identity, self.root)
        result = w.replay.historical_reconstruct(self.token, self.root)
        self.assertEqual(result["capability"], "UNAVAILABLE")
        self.assertIsNone(result["historical_view"])
        self.assertEqual(w.calls, 0)
        # A second manifest has its own current grant; deny all reconstruction data grants.
        _, root2 = w.reinterpret((w.work,), w.old_protocol.ref, "r2")
        for root in w.roots:
            w.security.revoke("C-replay-data-"+root.identity, root)
        result = w.replay.historical_reconstruct(self.token, root2)
        self.assertEqual(result["reasons"], ["DataAuthorityDenied"])
        self.assertIsNone(result["historical_view"])

    def test_missing_provider_does_not_affect_historical_output_or_silently_fallback(self):
        w = self.w
        del w.models["fixture-model:r1"]
        history = w.replay.historical_reconstruct(self.token, self.root)
        self.assertEqual(history["capability"], "FULL")
        self.assertEqual(w.replay.reexecute(self.token, self.root, "fixture-model:r1")["capability"], "UNAVAILABLE")
        self.assertEqual(w.calls, 0)
        result = w.replay.reexecute(self.token, self.root, "fixture-model:r2")
        self.assertEqual(result["capability"], "PARTIAL")
        self.assertIsNone(result["historical_view"])
        self.assertEqual(len(w.h.states.records()), 1)
        self.assertNotEqual(result["generated_output"], w.h.get(self.output).payload)

    def test_raw_removal_is_real_and_never_repaired_from_recorded_output(self):
        w = self.w
        w.artifacts.remove_fixture(w.artifact, "fixture")
        self.assertNotIn(w.artifact, w.artifacts._values)
        result = w.replay.historical_reconstruct(self.token, self.root)
        self.assertEqual(result["capability"], "PARTIAL")
        self.assertEqual(result["historical_view"]["raw_artifacts"], {})
        self.assertEqual(w.replay.reexecute(self.token, self.root, "fixture-model:r2")["capability"], "UNAVAILABLE")
        self.assertEqual(w.calls, 0)
        with self.assertRaises(ContractError):
            w.artifacts.put_fixture(w.artifact, "replacement")

    def test_missing_history_and_corrupt_artifact_are_honest_gaps(self):
        w = self.w
        missing = Ref(Space.EXECUTION, self.root.identity, "missing")
        self.assertEqual(w.replay.historical_reconstruct(self.token, missing)["capability"], "UNAVAILABLE")
        w.artifacts._values[w.artifact] = "injected corruption"
        result = w.replay.historical_reconstruct(self.token, self.root)
        self.assertEqual(result["reasons"], ["RawArtifactDigestMismatch"])
        self.assertEqual(result["historical_view"]["raw_artifacts"], {})

    def test_permission_revocation_during_reexecution_does_not_return_new_output(self):
        w = self.w
        def callback(*args):
            w.security.revoke("C-replay-"+self.root.identity, self.root)
            return {"description": "must not escape"}
        w.models["fixture-model:r1"] = callback
        result = w.replay.reexecute(self.token, self.root, "fixture-model:r1")
        self.assertEqual(result["capability"], "UNAVAILABLE")
        self.assertIsNone(result["generated_output"])

    def test_retention_during_reexecution_is_rechecked(self):
        w = self.w
        def callback(*args):
            w.artifacts.remove_fixture(w.artifact, "during execution")
            return {"description": "must not escape"}
        w.models["fixture-model:r1"] = callback
        result = w.replay.reexecute(self.token, self.root, "fixture-model:r1")
        self.assertEqual(result["capability"], "UNAVAILABLE")
        self.assertIsNone(result["generated_output"])
