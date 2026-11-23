"""学习助手候选只表达本增量允许的回复，正式状态由程序决定。"""

from typing import Annotated, Literal

from deermind.abstractions.events import FactModel
from deermind.spaces.interaction.memory_facts import Remember
from deermind.spaces.interaction.teaching_flow import TeachingProposal
from deermind.spaces.interaction.teaching_questions import TeachingQuestion
from pydantic import StringConstraints


class ReplyCandidate(FactModel):
    intent: Literal[
        "free_chat",
        "clarify",
        "explanation",
        "question_answer",
        "learning",
        "feedback",
        "detection",
        "detection_help",
        "memory_summary",
    ]
    wording: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]
    topic: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=48)]
    teaching: TeachingProposal | None = None
    question: TeachingQuestion | None = None
    verdict: Literal["correct", "incorrect", "partial", "uncertain"] | None = None
    help_quote: str | None = None
    memory: Remember | None = None
