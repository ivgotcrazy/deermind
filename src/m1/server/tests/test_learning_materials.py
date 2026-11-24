"""Supplemental reads preserve fixed permissions, whole content and model budgets."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from deermind.abstractions.ai.contracts import CallHandle
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import Ref
from deermind.spaces.interaction.learning_materials import (
    MATERIAL_BYTES,
    TOOL_REFS,
    ReadableMaterial,
    course_result,
    read_activity,
    reply_materials,
    selected_reference,
)
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncConnection


class LearningMaterialTests(TestCase):
    def test_fixed_number_only_exposes_label_and_matching_tool(self) -> None:
        origin = Ref(owner="interaction", type="student_input", id="origin")
        course = Ref(owner="product", type="material_candidate", id="fixed-chapter", revision=1)
        material = ReadableMaterial(kind="course", label="一段原文", reference=course)
        header = canonical_json({"readable_materials": [material.model_dump(mode="json")]})
        prompt, refs, tools = reply_materials(header, origin)
        self.assertEqual(refs, [origin, course])
        self.assertEqual(tools, [TOOL_REFS["course"]])
        self.assertNotIn("fixed-chapter", prompt)
        self.assertIn('"number":1', prompt)
        handle = Mock(spec=CallHandle)
        handle.input = SimpleNamespace(material_refs=refs)
        self.assertEqual(selected_reference(handle, "course", 1), course)
        self.assertIsNone(selected_reference(handle, "activity", 1))
        self.assertIsNone(selected_reference(handle, "course", 2))
        self.assertEqual(
            reply_materials('{"mode":"detection_message"}', origin),
            ('{"mode":"detection_message"}', [origin], []),
        )

    def test_large_course_material_offers_whole_blocks(self) -> None:
        reference = Ref(owner="domain", type="task", id="fixed-task", version=1)
        block: JsonValue = {"text": "a" * 5_000, "formula": "1/4"}
        material: JsonValue = {"responsibility": {"blocks": [block, block]}}
        response = course_result(material, [reference], None)
        self.assertEqual(response.data["sections"], ["responsibility:1", "responsibility:2"])
        section = course_result(material, [reference], "responsibility:2")
        self.assertEqual(section.data["material"], {"blocks": [block]})
        self.assertLessEqual(
            len(canonical_json(section.model_dump(mode="json")).encode()), MATERIAL_BYTES
        )


class ActivityReadTests(IsolatedAsyncioTestCase):
    async def test_earlier_page_uses_fixed_scope_bounds_and_five_whole_messages(self) -> None:
        scope, activity = uuid4(), uuid4()
        fixed = Ref(owner="interaction", type="activity_history", id=str(activity), path="/21")
        db = AsyncMock(spec=AsyncConnection)
        db.execute.return_value = Mock()
        db.execute.return_value.all.return_value = [
            SimpleNamespace(
                message_seq=seq, message_id=uuid4(), role="student", parts=[{"text": str(seq)}]
            )
            for seq in range(20, 14, -1)
        ]
        page = await read_activity(db, scope, fixed, None)
        messages = page.data["messages"]
        self.assertIsInstance(messages, list)
        assert isinstance(messages, list)
        self.assertEqual(len(messages), 5)
        self.assertEqual(page.data["next_before"], 16)
        params = db.execute.await_args.args[1]
        self.assertEqual((params["scope"], params["id"], params["before"]), (scope, activity, 21))
        self.assertEqual((await read_activity(db, scope, fixed, 25)).status, "not_found")
