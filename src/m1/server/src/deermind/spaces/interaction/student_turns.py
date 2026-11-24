"""Coordinate the accepted student reply and its transaction."""

from uuid import NAMESPACE_URL, UUID, uuid5

from deermind.abstractions.ai.contracts import ExecutionConfig
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.executions import Execution, RunInput
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.executions import store
from deermind.spaces.interaction import conversation_facts as facts
from deermind.spaces.interaction import (
    history,
)
from deermind.spaces.interaction.answer_feedback import read_answer_context, save_answer_feedback
from deermind.spaces.interaction.blueprints import entry_node
from deermind.spaces.interaction.conversation import (
    Conversation,
)
from deermind.spaces.interaction.learning_materials import CourseIndex, ReadCourse
from deermind.spaces.interaction.public import (
    ConfigView,
)
from deermind.spaces.interaction.reply_candidate import ReplyCandidate
from deermind.spaces.interaction.student_context import (
    ActivityConfig,
    ReadChapter,
    ReadMastery,
    StudentContext,
)
from deermind.spaces.interaction.teaching_questions import (
    TeachingCard,
)
from deermind.spaces.interaction.teaching_turn import apply_teaching_turn
from deermind.spaces.interaction.turn_requests import SpaceAdoption, TurnRequests
from deermind.spaces.interaction.turn_result import Reply, TeachingReply, TurnOutcome, complete_turn
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class StudentTurns:
    """空间内只接受一个交流输入，完成和停止竞争同一提交资格。"""

    def __init__(
        self,
        conversation: Conversation,
        current_adoption: SpaceAdoption,
        attachments: FactAttachments,
        queue: str,
        config: ExecutionConfig | None,
        activity_config: ActivityConfig,
        read_chapter: ReadChapter,
        read_mastery: ReadMastery | None = None,
        course_index: CourseIndex | None = None,
        read_course: ReadCourse | None = None,
    ) -> None:
        self.conversation = conversation
        self.engine = conversation.engine
        self.requests = TurnRequests(conversation, current_adoption, attachments, queue, config)
        self.current_adoption = current_adoption
        self.activity_config = activity_config
        self.read_course = read_course
        self.registry = self.requests.registry
        self.context_builder = StudentContext(
            conversation, self.registry, activity_config, read_chapter, read_mastery, course_index
        )

    async def finish(
        self,
        run: RunInput,
        candidate: ReplyCandidate,
        candidate_id: UUID,
        card: TeachingCard | None = None,
        *,
        post_close: bool = False,
    ) -> None:
        config = None
        parent_config = None
        bundle = None
        async with self.engine.connect() as db:
            original = await store.load(db, run.execution_id)
            grant = await store.authorization(db, run.execution_id)
            current = await history.current(db, original.scope_id)
            leaf = current.current_activity
            requested = candidate.teaching
            if requested and candidate.intent in {"explanation", "question_answer"}:
                position = (
                    "current"
                    if leaf and leaf.type == candidate.intent and requested.placement == "continue"
                    else "entry"
                )
                context_id = uuid5(
                    NAMESPACE_URL, f"{run.execution_id}:{candidate.intent}:{position}"
                )
                raw = await db.scalar(
                    text(
                        "SELECT to_jsonb(c)-'source_event_id' FROM interaction.context_bundles c "
                        "WHERE bundle_id=:id AND run_ref=:run"
                    ),
                    {"id": context_id, "run": run.execution_id},
                )
                if raw is not None:
                    bundle = facts.ContextFact.model_validate_json(canonical_json(raw))
            parent = (
                await history.activity_at(db, original.scope_id, leaf.activity_ref.activity_id)
                if leaf and (leaf.type in {"explanation", "question_answer"} or post_close)
                else None
            )
        teaching_intent = ("explanation", "question_answer")
        teaching = candidate.intent in teaching_intent or (
            parent is not None and candidate.intent != "learning"
        )
        if bundle is not None:
            config, _course = await self.activity_config(
                original.scope_id, bundle.adoption_ref, bundle.purpose, bundle.config_ref
            )
            if parent and bundle.activity_revision_ref is None:
                parent_config, _course = await self.activity_config(
                    original.scope_id,
                    parent.identity.adoption_ref,
                    parent.identity.type,
                    parent.identity.config_ref,
                )
        elif candidate.intent == "free_chat" and leaf is None:
            config, _course = await self.activity_config(
                original.scope_id, UUID(grant.basis_refs[0].id), "free_chat", None
            )
        async with self.engine.begin() as db:
            saved = await store.lock_owned(db, self.registry, run.execution_id)
            if saved.state == "completed":
                return
            work = await store.active(db, self.registry, run, "finish")
            practice = await read_answer_context(db, UUID(work.input_ref.id))
            position = await history.current(db, work.scope_id)
            if practice is not None:
                if candidate.intent == "feedback" and candidate.verdict is not None:
                    await save_answer_feedback(
                        self.conversation, db, work, candidate, candidate_id, practice
                    )
                    outcome, reply = "completed", candidate.wording
                else:
                    outcome, reply = "blocked", "作答已保存，暂时无法给出本题反馈。"
            elif position.current_round and (
                not post_close
                or position.current_round.state != "closed"
                or requested is None
                or requested.placement != "child"
                or candidate.intent not in teaching_intent
            ):
                outcome, reply = "needs_input", "你可以提交本题。需要讲解或提示时，可以直接提出。"
            elif candidate.question and card is None:
                outcome, reply = "blocked", "暂时没有准备好符合要求的题，可以继续当前内容。"
            elif teaching:
                outcome, reply = await apply_teaching_turn(
                    self.conversation,
                    db,
                    work,
                    candidate,
                    config,
                    parent_config,
                    bundle,
                    candidate_id,
                )
            else:
                outcome, reply = await self._interpret(db, work, candidate, config)
            if card and outcome == "completed":
                reply = (
                    "可以先试着完成这道练习。"
                    if card.part.purpose == "practice"
                    else "我们看这道例题。"
                )
            teaching_reply = (
                outcome == "completed"
                and practice is None
                and candidate.intent in teaching_intent
                and candidate.question is None
                and card is None
            )
            content = (
                TeachingReply(reply, candidate.memory)
                if teaching_reply
                else Reply(reply, card if outcome == "completed" else None)
            )
            await complete_turn(self.conversation, db, self.registry, run, work, outcome, content)

    async def acknowledge_answer(self, run: RunInput) -> None:
        async with self.engine.begin() as db:
            existing = await store.lock_owned(db, self.registry, run.execution_id)
            if existing.state == "completed":
                return
            work = await store.active(db, self.registry, run, "finish")
            answer = await read_answer_context(db, UUID(work.input_ref.id))
            if answer is None or answer.round_id is None:
                raise ValueError("An accepted detection answer is required")
            await complete_turn(
                self.conversation,
                db,
                self.registry,
                run,
                work,
                "completed",
                Reply("作答已保存，可以继续下一题。"),
            )

    async def _interpret(
        self,
        db: AsyncConnection,
        work: Execution,
        candidate: ReplyCandidate,
        config: ConfigView | None,
    ) -> tuple[TurnOutcome, str]:
        if candidate.intent == "clarify":
            return "needs_input", candidate.wording
        if candidate.intent == "learning":
            return "blocked", "这个请求需要讲解、答疑或检测。当前还无法开展该活动。"
        current = await history.current(db, work.scope_id)
        if current.current_activity is not None:
            return "completed", candidate.wording
        if config is None or config.gaps:
            return "blocked", "这门课程暂未配置自由交谈，请联系管理员。"
        entry = entry_node(config.definition.blueprint)
        start = next(node for node in config.definition.blueprint.nodes if node.node_id == "start")
        if entry is None or "reply" not in entry.allowed_actions:
            return "blocked", start.fallback.explanation
        trigger = await db.scalar(
            text("SELECT source_event_id FROM interaction.inputs WHERE input_id=:id"),
            {"id": UUID(work.input_ref.id)},
        )
        if not isinstance(trigger, UUID):
            raise RuntimeError("Student input is missing its source event")
        grant = await store.authorization(db, work.execution_id)
        await self.conversation.begin(
            db,
            work.scope_id,
            UUID(grant.initiator_ref.id),
            grant.basis_refs[0],
            config.config_ref,
            config.definition,
            "free_chat",
            candidate.topic,
            trigger,
            parent_id=None,
            input_id=UUID(work.input_ref.id),
            initial_node=entry.node_id,
            request_ref=UUID(work.acceptance_key),
        )
        return "completed", candidate.wording
