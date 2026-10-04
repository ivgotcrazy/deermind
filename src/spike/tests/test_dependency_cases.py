import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from foundation.cases import EvidenceRecorder, correct
from foundation.dependency_cases import DependencyWorld
from foundation.records import Space
from foundation.runtime import Harness


class DependencyCommitTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.evidence = EvidenceRecorder(Path(self.directory.name) / "evidence.jsonl")
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.evidence.close)

    def test_chain_uses_real_commits_without_seeding_derived_standing(self):
        original = Harness.seed_committed_fixture
        def guarded(h, record):
            self.assertNotEqual(record.ref.space, Space.DERIVED)
            return original(h, record)
        with patch.object(Harness, "seed_committed_fixture", guarded):
            world = DependencyWorld(self.evidence)
            o = world.submit("Observation", "O", "r1", world.work)
            e = world.submit("Evidence", "E-0", "r1", o)
            b = world.submit("LearnerBelief", "B-0", "r1", e)
            world.stage("current", {"O": o, "E-0": e, "B-0": b})
            world.preserve(world.h.states.records())
        self.assertTrue(all(c["passed"] for c in self.evidence.checks))

    def test_other_owner_cannot_commit_and_revocation_blocks_owner(self):
        w = DependencyWorld(self.evidence)
        o = w.submit("Observation", "O", "r1", w.work)
        prepared = w.prepare("Evidence", "E-0", "r1", o)
        w.finish(prepared, "Unauthorized", token=w.tokens["interaction"])
        w.security.revoke("Evidence-commit", prepared[1].execution)
        w.finish(prepared, "Unauthorized")
        self.assertIsNone(w.h.get(prepared[1].record.ref))
        self.assertTrue(all(c["passed"] for c in self.evidence.checks))

    def test_new_upstream_head_does_not_rescue_inflight_old_candidate(self):
        w = DependencyWorld(self.evidence)
        o = w.submit("Observation", "O", "r1", w.work)
        prepared = w.prepare("Evidence", "E-0", "r1", o)
        correct(w.h, o)
        new_o = w.submit("Observation", "O", "r2", w.work)
        w.finish(prepared, "CandidateStale")
        e = w.submit("Evidence", "E-0", "r2", new_o)
        self.assertEqual(w.h.get(e).dependencies[0].target, new_o)
        self.assertTrue(all(c["passed"] for c in self.evidence.checks))
