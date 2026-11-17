"""验证使用条件不把登录、监护身份核实或缺失的确认当成同意。"""

import unittest
from datetime import UTC, datetime
from uuid import uuid4

from deermind.abstractions.events import Ref
from deermind.product.accounts.conditions import derive_conditions
from deermind.product.accounts.usage_facts import ConditionsFact, ConfirmationFact


class UsageConditionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.student = uuid4()
        self.now = datetime.now(UTC)
        self.notice = Ref(owner="product", type="usage_notice", id="synthetic-test", revision=1)
        self.guardian = ConfirmationFact(
            confirmation_id=uuid4(),
            student_id=self.student,
            kind="guardian_consent",
            notice_ref=self.notice,
            decision="accepted",
            source_ref=Ref(owner="product", type="offline_verification", id="synthetic-test"),
            actor_ref=Ref(owner="product", type="account", id=str(uuid4())),
            occurred_at=None,
            created_at=self.now,
        )
        self.assent = self.guardian.model_copy(
            update={"confirmation_id": uuid4(), "kind": "student_assent"}
        )

    def calculate(
        self, confirmations: list[ConfirmationFact], verified: bool = True
    ) -> ConditionsFact:
        return derive_conditions(
            student_id=self.student,
            revision=1,
            now=self.now,
            notice_ref=self.notice,
            guardian_verified=verified,
            confirmations=confirmations,
        )

    def test_missing_confirmation_is_not_agreement(self) -> None:
        self.assertEqual(self.calculate([]).eligibility, "pending")
        for partial in ([self.guardian], [self.assent]):
            with self.subTest(kind=partial[0].kind):
                self.assertEqual(self.calculate(partial).eligibility, "pending")
        result = self.calculate([self.guardian, self.assent])
        self.assertEqual(result.eligibility, "allowed")
        self.assertEqual(len(result.confirmation_refs), 2)
        self.assertEqual(result.reasons, [])

    def test_unverified_relationship_and_decline_block_use(self) -> None:
        self.assertEqual(self.calculate([self.guardian, self.assent], False).eligibility, "pending")
        refusal = self.assent.model_copy(update={"decision": "declined"})
        result = self.calculate([self.guardian, refusal])
        self.assertEqual(result.eligibility, "blocked")
        self.assertEqual(result.reasons[0].code, "student_assent_declined")

    def test_other_student_old_notice_and_duplicate_are_rejected(self) -> None:
        invalid = [
            [self.guardian.model_copy(update={"student_id": uuid4()})],
            [
                self.assent.model_copy(
                    update={"notice_ref": self.notice.model_copy(update={"revision": 2})}
                )
            ],
            [self.assent, self.assent],
        ]
        for facts in invalid:
            with self.subTest(facts=facts), self.assertRaises(ValueError):
                self.calculate(facts)
