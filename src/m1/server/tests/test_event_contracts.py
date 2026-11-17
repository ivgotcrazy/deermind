"""离线验证事实正文边界；事务、权限和并发由真实PG测试承担。"""

import json
import unittest
from uuid import uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import Ref
from deermind.bootstrap.events import event_store
from deermind.foundation.system.events.store import EventStore
from deermind.product.accounts.facts import ACCOUNT_REGISTRATION, AccountFact
from pydantic import ValidationError


class EventContractTests(unittest.TestCase):
    def test_complete_fact_rejects_invalid_inputs(self) -> None:
        """历史正文不能依赖默认补列、静默类型转换或未知字段。"""
        content: dict[str, object] = {
            "account_id": str(uuid4()),
            "login_identifier": "admin",
            "display_name": "管理员",
            "role": "admin",
            "status": "active",
            "revision": 1,
            "created_at": "2026-11-16T01:00:00Z",
        }
        AccountFact.model_validate_json(json.dumps(content))
        cases = [
            {key: value for key, value in content.items() if key != "created_at"},
            {**content, "revision": "1"},
            {**content, "password": "must-not-be-saved"},
            {**content, "created_at": "2026-11-16T01:00:00"},
            {**content, "login_identifier": " Admin "},
        ]
        for invalid in cases:
            with self.subTest(keys=list(invalid)), self.assertRaises(ValidationError):
                AccountFact.model_validate_json(json.dumps(invalid))

    def test_reference_has_one_version_kind(self) -> None:
        with self.assertRaises(ValidationError):
            Ref(owner="product", type="account", id="123", revision=1, version=1)

    def test_registry_rejects_duplicate_definition(self) -> None:
        event_store()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            EventStore([ACCOUNT_REGISTRATION, ACCOUNT_REGISTRATION])

    def test_digest_encoding_is_stable_and_finite(self) -> None:
        self.assertEqual(
            canonical_json({"b": 2, "a": "中文"}), canonical_json({"a": "中文", "b": 2})
        )
        for invalid in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                canonical_json({"value": invalid})


if __name__ == "__main__":
    unittest.main(verbosity=2)
