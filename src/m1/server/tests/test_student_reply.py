"""学生端只接收程序登记的候选结构。"""

import json
from unittest import TestCase

from deermind.bootstrap.student_operation import rule_review_context
from deermind.spaces.domain.generated_tasks import paragraph
from deermind.spaces.interaction.public import QuestionPart
from deermind.spaces.interaction.reply_candidate import ReplyCandidate
from pydantic import ValidationError


class StudentReplyTests(TestCase):
    def test_practice_card_never_carries_worked_solution(self) -> None:
        data = {
            "part_id": "practice",
            "type": "question",
            "purpose": "practice",
            "title": "练习",
            "task_use_ref": {"owner": "interaction", "type": "task_use", "id": "task-1"},
            "statement": paragraph("求新量", "statement"),
            "worked_solution": paragraph("结果是 25", "reference"),
        }
        with self.assertRaises(ValidationError):
            QuestionPart.model_validate(data)
        self.assertIsNone(
            QuestionPart.model_validate({**data, "worked_solution": None}).worked_solution
        )

    def test_wrong_parent_rule_is_reviewed_using_only_child_configuration(self) -> None:
        candidate = ReplyCandidate.model_validate(
            {
                "intent": "explanation",
                "wording": "先说单位一。",
                "topic": "单位一",
                "teaching": {
                    "action": "reply",
                    "placement": "child",
                    "placement_quote": "先讲单位一",
                    "conditions": [],
                    "rules": [
                        {
                            "rule_id": "parent-rule",
                            "status": "satisfied",
                            "input_quote": None,
                        }
                    ],
                },
            }
        )
        selected = {
            "activity_type": "explanation",
            "position": "entry",
            "rules": [{"ref": {"id": "child-rule"}}],
        }
        delimiter = "\n本轮输入（JSON）\n"
        context = (
            json.dumps(
                {
                    "activity": {"type": "question_answer"},
                    "recent": ["旧请求"],
                    "teaching_contexts": [
                        {"activity_type": "question_answer", "position": "current", "rules": []},
                        selected,
                    ],
                }
            )
            + delimiter
            + '{"text":"先讲单位一"}'
        )
        review, _, original = rule_review_context(context, candidate).partition(delimiter)
        self.assertEqual(json.loads(review)["teaching_contexts"], [selected])
        self.assertNotIn("旧请求", review)
        self.assertEqual(json.loads(original)["text"], "先讲单位一")

    def test_candidate_cannot_request_an_unregistered_activity_action(self) -> None:
        wording = {"intent": "clarify", "wording": "你想了解哪个问题？", "topic": "补充问题"}
        self.assertEqual(ReplyCandidate.model_validate(wording).intent, "clarify")
        for change in ({"intent": "start_detection"}, {"action": "start_detection"}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                ReplyCandidate.model_validate({**wording, **change})
