"""工作记忆只保存可从本轮正式内容核对的条目。"""

from unittest import TestCase
from uuid import uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import InlineContent
from deermind.spaces.interaction.conversation_facts import ref
from deermind.spaces.interaction.memory_facts import MemoryRevision, Remember, remember, revise


class StudentMemoryTests(TestCase):
    def test_unquoted_preference_cannot_be_saved(self) -> None:
        """模型猜出的偏好没有学生原话，直接忽略。"""
        proposal = Remember(type="explicit_preference", quote="我一直偏好图示")
        self.assertIsNone(
            remember(
                proposal,
                "请继续原来的例子",
                "先看一段例子",
                ref("input", uuid4()),
                ref("message", uuid4()),
                None,
            )
        )

    def test_resolution_requires_a_quote_from_the_formal_reply(self) -> None:
        """保存的问题沿原编号解决，核对原条目和正式回复。"""
        student = ref("input", uuid4())
        response = ref("message", uuid4())
        entries = remember(
            Remember(type="pending_question", quote="为什么还要加回原量？"),
            "为什么还要加回原量？我没看懂。",
            "我们接着看。",
            student,
            response,
            None,
        )
        assert entries is not None
        saved = revise(
            uuid4(),
            ref("activity", uuid4(), 1),
            student,
            "entries",
            8,
            {"entries": [item.model_dump(mode="json") for item in entries]},
            [student],
            None,
        )
        content = saved.records[0].content
        assert isinstance(content, InlineContent)
        previous = MemoryRevision.model_validate_json(canonical_json(content.value))
        proposal = Remember(
            type="pending_question",
            quote="新量包含原量和增加量",
            resolves=entries[0].entry_id,
        )
        self.assertIsNone(remember(proposal, "", "换个话题", student, response, previous))
        resolved = remember(
            proposal,
            "",
            "新量包含原量和增加量。",
            student,
            response,
            previous,
        )
        assert resolved is not None
        self.assertEqual(resolved[0].state, "resolved")
        self.assertEqual(resolved[0].resolution_refs, [response])
        self.assertEqual(resolved[0].source_refs, [student])
