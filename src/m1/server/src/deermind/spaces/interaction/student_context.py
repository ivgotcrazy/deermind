"""Build the learning assistant context and record the teaching materials used by the run."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Execution, RunInput
from deermind.foundation.ai import store as ai_store
from deermind.foundation.system.executions import store
from deermind.foundation.system.executions.contracts import Registry
from deermind.product.public.courses import CourseSnapshot
from deermind.spaces.domain.public import TaskInstance
from deermind.spaces.interaction import conversation_facts as facts
from deermind.spaces.interaction import history, memory_facts
from deermind.spaces.interaction.answer_feedback import read_answer_context
from deermind.spaces.interaction.blueprints import effective_binding, entry_node
from deermind.spaces.interaction.conversation import Conversation, draft, ref
from deermind.spaces.interaction.learning_materials import TOOL_REFS, CourseIndex, activity_index
from deermind.spaces.interaction.public import ActivityType, ConfigView, StudentInput
from deermind.spaces.interaction.teaching_questions import teaching_options
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

ACKNOWLEDGE_ANSWER = "acknowledge_detection_answer"
type ActivityConfig = Callable[
    [UUID, UUID, ActivityType, UUID | None], Awaitable[tuple[ConfigView | None, CourseSnapshot]]
]
type ReadQuestion = Callable[[AsyncConnection, Ref], Awaitable[TaskInstance | None]]
type ReadChapter = Callable[[UUID, UUID, Ref], Awaitable[list[dict[str, JsonValue]]]]
type ReadMastery = Callable[[UUID, UUID, Ref | None], Awaitable[dict[str, JsonValue]]]


class StudentContext:
    """Select authorized materials and save the teaching context for the active run."""

    def __init__(
        self,
        conversation: Conversation,
        registry: Registry,
        activity_config: ActivityConfig,
        read_chapter: ReadChapter,
        read_mastery: ReadMastery | None,
        course_index: CourseIndex | None,
    ) -> None:
        self.conversation = conversation
        self.engine = conversation.engine
        self.registry = registry
        self.activity_config = activity_config
        self.read_chapter = read_chapter
        self.read_mastery = read_mastery
        self.course_index = course_index

    async def build(
        self,
        run: RunInput,
        question: ReadQuestion | None = None,
        *,
        post_close: bool = False,
        mastery_ref: Ref | None = None,
    ) -> str:
        """只从固定输入与当前活动取材。"""
        async with self.engine.begin() as db:
            work = await store.active(db, self.registry, run, "step")
            submission = await read_answer_context(db, UUID(work.input_ref.id))
            if submission is not None:
                if submission.round_id:
                    position = await history.current(db, work.scope_id)
                    fixed_round = position.current_round
                    if (
                        fixed_round
                        and fixed_round.can_continue
                        and fixed_round.round_ref.id == str(submission.round_id)
                    ):
                        return ACKNOWLEDGE_ANSWER
                related = await question(db, submission.instance_ref) if question else None
                fixed = related.model_dump(mode="json") if related else None
                return (
                    canonical_json({"mode": "answer_feedback", "question": fixed})
                    + "\n本轮输入（JSON）\n"
                    + canonical_json(submission.answer)
                )
            raw = await db.scalar(
                text("SELECT input FROM interaction.inputs WHERE input_id=:id"),
                {"id": UUID(work.input_ref.id)},
            )
            current = await history.current(db, work.scope_id)
            assessment = current.current_round
            if post_close and (assessment is None or assessment.state != "closed"):
                raise RuntimeError("Post-round help requires a closed round")
            if assessment and not post_close:
                detection: dict[str, JsonValue] = {
                    "mode": "detection_message",
                    "round_state": assessment.state,
                }
                if (
                    assessment.state == "open"
                    and self.course_index
                    and (await self._reads_enabled(db, work))
                ):
                    detection["question"] = await db.scalar(
                        text(
                            "SELECT statement FROM interaction.task_uses "
                            "WHERE scope_id=:scope AND task_use_id=:id"
                        ),
                        {"scope": work.scope_id, "id": UUID(assessment.task_use_ref.id)},
                    )
                return canonical_json(detection) + "\n本轮输入（JSON）\n" + canonical_json(raw)
            fixed_question = None
            if post_close and assessment and question:
                source = await db.scalar(
                    text(
                        "SELECT instance_ref FROM interaction.task_uses "
                        "WHERE scope_id=:scope AND task_use_id=:id"
                    ),
                    {"scope": work.scope_id, "id": UUID(assessment.task_use_ref.id)},
                )
                if source is not None:
                    fixed_question = await question(db, Ref.model_validate(source))
            grant = await store.authorization(db, work.execution_id)
            leaf = current.current_activity
            active = (
                await history.activity_at(db, work.scope_id, leaf.activity_ref.activity_id)
                if leaf
                else None
            )
            memories = (
                await memory_facts.read(db, work.scope_id, leaf.activity_ref.activity_id)
                if leaf
                else []
            )
            covered_through = next(
                (item.basis_message_seq for item in memories if item.kind == "summary"), 0
            )
            # 摘要未保存时，继续读取本轮能放入预算的原消息。
            recent = await db.execute(
                text(
                    "SELECT m.message_id,m.message_seq,m.role,m.parts FROM interaction.messages m "
                    "LEFT JOIN interaction.message_assignments a ON a.message_id=m.message_id "
                    "WHERE m.scope_id=:scope AND m.source_input_ref IS DISTINCT FROM :input "
                    "AND a.activity_id IS NOT DISTINCT FROM CAST(:activity AS uuid) "
                    "AND m.role IN ('student','assistant') AND m.message_seq>:covered "
                    "ORDER BY m.message_seq DESC LIMIT :limit"
                ),
                {
                    "scope": work.scope_id,
                    "input": UUID(work.input_ref.id),
                    "activity": leaf.activity_ref.activity_id if leaf else None,
                    "covered": covered_through,
                    "limit": memory_facts.HISTORY_WINDOW,
                },
            )
            history_text: list[dict[str, JsonValue]] = []
            message_refs: list[Ref] = []
            before = current.latest_message_seq + 1
            remaining = 32 * 1024
            for item in recent.mappings():
                message: dict[str, JsonValue] = {"role": item["role"], "parts": item["parts"]}
                remaining -= len(canonical_json(message).encode("utf-8"))
                if remaining < 0:
                    break
                history_text.append(message)
                message_refs.append(ref("message", item["message_id"]))
                before = item["message_seq"]
            allow_reads = (
                self.course_index is not None
                and mastery_ref is None
                and (active is None or str(active.identity.adoption_ref) == grant.basis_refs[0].id)
                and await self._reads_enabled(db, work)
            )
            readable = (
                await activity_index(
                    db,
                    work.scope_id,
                    UUID(grant.basis_refs[0].id),
                    before,
                    [item.activity_ref.activity_id for item in current.path],
                )
                if allow_reads
                else []
            )
        source = StudentInput.model_validate_json(canonical_json(raw))
        contexts: list[dict[str, JsonValue]] = []
        quoted: list[dict[str, JsonValue]] = []
        adoption_id = UUID(grant.basis_refs[0].id)
        for reference in source.explicit_refs:
            parts = await self.read_chapter(work.scope_id, adoption_id, reference)
            if len(canonical_json(parts).encode()) <= 16 * 1024:
                quoted.append(
                    {
                        "ref": reference.model_dump(mode="json"),
                        "parts": [item for item in parts],
                    }
                )
            else:
                quoted.append(
                    {
                        "ref": reference.model_dump(mode="json"),
                        "omission": "章节超出本轮取材范围，请学生指出具体段落。",
                    }
                )
        adoption = active.identity.adoption_ref if active else adoption_id
        if active is None or active.identity.type != "detection" or post_close:
            kinds: tuple[ActivityType, ...] = ("explanation", "question_answer")
            for kind in kinds:
                positions: list[history.ActivityState | None] = [None]
                if active and active.identity.type == kind:
                    positions.append(active)
                for position in positions:
                    config, course = await self.activity_config(
                        work.scope_id,
                        adoption,
                        kind,
                        position.identity.config_ref if position else None,
                    )
                    if config is not None and not config.gaps:
                        chosen = await self._prepare_lesson(
                            run,
                            work,
                            adoption,
                            config,
                            course,
                            position,
                            [*message_refs, *source.explicit_refs],
                            [value.identity for value in memories],
                        )
                        if chosen is not None:
                            contexts.append(chosen)
        if allow_reads and self.course_index:
            async with self.engine.connect() as db:
                readable.extend(
                    await self.course_index(db, work.scope_id, adoption, source.explicit_refs)
                )
            mastery: dict[str, JsonValue] | None = {
                "state": "reference_available"
                if any(item.reference.type == "mastery_snapshot" for item in readable)
                else "unknown",
            }
        else:
            mastery = (
                await self.read_mastery(work.scope_id, adoption, mastery_ref)
                if self.read_mastery
                else None
            )
        return (
            canonical_json(
                {
                    "mode": "post_detection_help" if post_close else "conversation",
                    "question": fixed_question.model_dump(mode="json") if fixed_question else None,
                    "quoted_material": quoted,
                    "memory": [value.content for value in memories],
                    "activity": current.current_activity.model_dump(mode="json")
                    if current.current_activity
                    else None,
                    "recent": list(reversed(history_text)),
                    "teaching_contexts": contexts,
                    "published_mastery": mastery,
                    **(
                        {"readable_materials": [item.model_dump(mode="json") for item in readable]}
                        if readable
                        else {}
                    ),
                }
            )
            + "\n本轮输入（JSON）\n"
            + canonical_json(raw)
        )

    @staticmethod
    async def _reads_enabled(db: AsyncConnection, work: Execution) -> bool:
        config = await ai_store.configuration(db, work.execution_id)
        return config.budget.max_tool_attempts > 0 and any(
            ref in binding.tool_refs
            for binding in config.purpose_bindings.values()
            for ref in TOOL_REFS.values()
        )

    async def _prepare_lesson(
        self,
        run: RunInput,
        work: Execution,
        adoption: UUID,
        config: ConfigView,
        course: CourseSnapshot,
        activity: history.ActivityState | None,
        messages: list[Ref],
        memory_refs: list[Ref],
    ) -> dict[str, JsonValue] | None:
        definition = config.definition
        kind = definition.activity_type
        if kind != "explanation" and kind != "question_answer":
            raise ValueError("Expected a teaching activity configuration")
        node = (
            next(
                item
                for item in definition.blueprint.nodes
                if item.node_id == activity.position.node_id
            )
            if activity
            else entry_node(definition.blueprint)
        )
        if node is None:
            return None
        binding = effective_binding(definition, node.node_id)
        rules = [item for item in definition.rules if UUID(item.ref.id) in binding.rule_ids]
        strategies = [
            item for item in definition.strategies if UUID(item.ref.id) in binding.strategy_ids
        ]
        transitions = [
            edge
            for edge in definition.blueprint.transitions
            if edge.source_node_id == node.node_id and edge.when in {"on_input", "after_reply"}
        ]
        position = "current" if activity else "entry"
        bundle_id = uuid5(NAMESPACE_URL, f"{work.execution_id}:{kind}:{position}")
        current_ref = (
            ref("activity", activity.identity.activity_id, activity.position.revision)
            if activity
            else None
        )
        source_refs = [
            work.input_ref,
            config.config_ref,
            Ref(owner="product", type="space_adoption", id=str(adoption)),
            *messages,
            *(rule.ref for rule in rules),
            *(strategy.ref for strategy in strategies),
        ]
        row = facts.ContextFact(
            bundle_id=bundle_id,
            scope_id=work.scope_id,
            run_ref=work.execution_id,
            source_ref=work.input_ref,
            purpose=kind,
            activity_revision_ref=current_ref,
            adoption_ref=adoption,
            config_ref=UUID(config.config_ref.id),
            materials=[{"ref": value.model_dump(mode="json")} for value in source_refs],
            memory_refs=memory_refs,
            publication_refs=[],
            omissions=[],
            created_at=datetime.now(UTC),
        )
        async with self.engine.begin() as db:
            await store.active(db, self.registry, run, "step")
            existing = await db.scalar(
                text("SELECT bundle_id FROM interaction.context_bundles WHERE bundle_id=:id"),
                {"id": bundle_id},
            )
            if existing is None:
                authorization = await store.authorization(db, work.execution_id)
                request_id = await db.scalar(
                    text("SELECT request_id FROM interaction.inputs WHERE input_id=:id"),
                    {"id": UUID(work.input_ref.id)},
                )
                if not isinstance(request_id, str):
                    raise RuntimeError("Context must reference an accepted input")
                owner = ref("context_bundle", bundle_id)
                await self.conversation.append(
                    db,
                    work.scope_id,
                    UUID(authorization.initiator_ref.id),
                    UUID(work.acceptance_key),
                    [
                        draft(
                            work.scope_id,
                            facts.CONTEXT_PREPARED,
                            owner,
                            facts.ContextPrepared(
                                subject_ref=owner,
                                records=[facts.record(facts.CONTEXT, bundle_id, row)],
                            ),
                            request_id,
                        )
                    ],
                )
        return {
            "context_ref": str(bundle_id),
            "activity_type": kind,
            "position": position,
            "node": node.model_dump(mode="json"),
            "rules": [item.model_dump(mode="json") for item in rules],
            "strategies": [item.model_dump(mode="json") for item in strategies],
            "transitions": [item.model_dump(mode="json") for item in transitions],
            "course": {
                "textbook": course.textbook_title,
                "target": course.target_title,
                "items": [
                    {"title": item.title, "task_conditions": item.task_conditions.description}
                    for item in course.items
                ],
                "question_tasks": [
                    task.model_dump(mode="json") for task in teaching_options(course)
                ],
            },
        }
