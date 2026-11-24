"""Authorize a learning reply's supplemental reads and return bounded source material."""

from collections.abc import Awaitable, Callable, Sequence
from typing import Annotated, Literal
from uuid import UUID

from deermind.abstractions.ai.contracts import CallHandle
from deermind.abstractions.ai.tools import ToolResult
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import FactModel, Ref
from deermind.foundation.system.executions import store
from deermind.spaces.interaction import history
from pydantic import Field, JsonValue, TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

type ReadKind = Literal["activity", "course", "published"]
TOOL_REFS: dict[ReadKind, Ref] = {
    "activity": Ref(owner="interaction", type="tool", id="read_activity_material", revision=1),
    "course": Ref(owner="interaction", type="tool", id="read_course_material", revision=1),
    "published": Ref(owner="interaction", type="tool", id="read_published_state", revision=1),
}
MATERIAL_BYTES = 8 * 1024
PAGE_SIZE = 5
_LOCATIONS: dict[ReadKind, frozenset[tuple[str, str]]] = {
    "activity": frozenset(
        ("interaction", item) for item in ("activity_history", "message", "task_use", "help")
    ),
    "course": frozenset(
        {
            ("product", "material_candidate"),
            ("domain", "task"),
            ("domain", "solution"),
            ("domain", "task_instance"),
        }
    ),
    "published": frozenset({("evaluation", "mastery_snapshot"), ("evaluation", "goal_evaluation")}),
}
_INPUT_SECTION = "\n本轮输入（JSON）\n"
_CONTEXT = TypeAdapter(dict[str, JsonValue])


class ReadableMaterial(FactModel):
    kind: ReadKind
    label: str
    reference: Ref


class ReadMaterial(FactModel):
    """Numbers point to authorized references in the saved call input."""

    number: Annotated[int, Field(ge=1)]


class ReadPage(ReadMaterial):
    """The activity tool may continue before a previously reported message position."""

    before: Annotated[int, Field(ge=1)] | None = None


class ReadSection(ReadMaterial):
    section: Annotated[str, Field(min_length=1, max_length=80)] | None = None


_CATALOGUE = TypeAdapter(list[ReadableMaterial])
type CourseIndex = Callable[
    [AsyncConnection, UUID, UUID, Sequence[Ref]], Awaitable[list[ReadableMaterial]]
]
type ReadCourse = Callable[
    [AsyncConnection, UUID, UUID, Ref], Awaitable[tuple[JsonValue, list[Ref]] | None]
]


def reply_materials(context: str, origin: Ref) -> tuple[str, list[Ref], list[Ref]]:
    """Keep the numbered labels in the model input and the complete refs in the call record."""
    header, separator, tail = context.partition(_INPUT_SECTION)
    bundle = _CONTEXT.validate_json(header)
    raw = bundle.pop("readable_materials", None)
    if raw is None:
        return context, [origin], []
    items = _CATALOGUE.validate_json(canonical_json(raw))
    bundle["readable_materials"] = [
        {"number": number, "kind": item.kind, "label": item.label[:96]}
        for number, item in enumerate(items, start=1)
    ]
    return (
        canonical_json(bundle) + separator + tail,
        [origin, *(item.reference for item in items)],
        list(dict.fromkeys(TOOL_REFS[item.kind] for item in items)),
    )


def selected_reference(handle: CallHandle, kind: ReadKind, number: int) -> Ref | None:
    refs = handle.input.material_refs
    if not 1 <= number < len(refs):
        return None
    reference = refs[number]
    if (reference.owner, reference.type) not in _LOCATIONS[kind]:
        return None
    return reference


def result(data: dict[str, JsonValue], refs: Sequence[Ref] = ()) -> ToolResult:
    """Omit oversized objects whole so formulas, tables and quoted text stay intact."""
    value = ToolResult(status="ok", data=data, source_refs=list(refs), owner_receipt_ref=None)
    if len(canonical_json(value.model_dump(mode="json")).encode("utf-8")) <= MATERIAL_BYTES:
        return value
    return ToolResult(
        status="ok",
        data={"omission": "材料过长，请学生指出具体段落。"},
        source_refs=list(refs[:1]),
        owner_receipt_ref=None,
    )


def unavailable() -> ToolResult:
    return ToolResult(
        status="not_found",
        data={"reason": "本轮没有这份可读材料。"},
        source_refs=[],
        owner_receipt_ref=None,
    )


def course_result(body: JsonValue, refs: list[Ref], section: str | None) -> ToolResult:
    """Offer whole rich-content blocks when the complete material exceeds the limit."""
    whole = result({"material": body}, refs)
    if section is None and "omission" not in whole.data:
        return whole
    fields = body[0] if isinstance(body, list) and len(body) == 1 else body
    choices: dict[str, JsonValue] = {}
    if isinstance(fields, dict):
        for name, value in fields.items():
            if not isinstance(value, dict):
                continue
            blocks = value.get("blocks")
            if isinstance(blocks, list):
                for index, block in enumerate(blocks[:30], start=1):
                    choices[f"{name}:{index}"] = {**value, "blocks": [block]}
    if section is not None:
        return (
            result({"material": choices[section], "section": section}, refs)
            if section in choices
            else unavailable()
        )
    return (
        result({"omission": "材料过长，可按下列分段补读。", "sections": list(choices)}, refs)
        if choices
        else whole
    )


async def activity_index(
    db: AsyncConnection, scope: UUID, adoption: UUID, before: int, activities: Sequence[UUID]
) -> list[ReadableMaterial]:
    """List the authorized activity history and its latest presented question and help."""
    if not activities:
        return []
    items: list[ReadableMaterial] = []
    for activity in activities[-2:]:
        saved = await history.activity_at(db, scope, activity)
        items.append(
            ReadableMaterial(
                kind="activity",
                label=f"{saved.identity.name}的较早对话",
                reference=Ref(
                    owner="interaction",
                    type="activity_history",
                    id=str(activity),
                    path=f"/{before}",
                ),
            )
        )
    rows = (
        await db.execute(
            text("""
        SELECT 'task_use' AS kind,u.task_use_id AS id,m.message_seq,u.instance_ref
        FROM interaction.task_uses u JOIN interaction.messages m
          ON m.scope_id=u.scope_id AND m.message_id=u.provided_message_ref
        WHERE u.scope_id=:scope AND u.activity_id=ANY(:activities)
          AND u.adoption_ref=:adoption AND u.provided_message_ref IS NOT NULL
        UNION ALL
        SELECT 'help',h.help_id,m.message_seq,NULL::jsonb
        FROM interaction.help_facts h JOIN interaction.messages m
          ON m.scope_id=h.scope_id AND m.message_id::text=h.provided_part_refs->0->>'id'
        WHERE h.scope_id=:scope AND h.activity_id=ANY(:activities) AND h.stage='provided'
        ORDER BY message_seq DESC LIMIT 4
    """),
            {"scope": scope, "adoption": adoption, "activities": list(activities[-2:])},
        )
    ).all()
    for row in rows:
        label = "已呈现题面" if row.kind == "task_use" else "已提供的帮助"
        items.append(
            ReadableMaterial(
                kind="activity",
                label=label,
                reference=Ref(owner="interaction", type=row.kind, id=str(row.id)),
            )
        )
        if row.instance_ref is not None:
            items.append(
                ReadableMaterial(
                    kind="course",
                    label="已呈现题目的课程资料",
                    reference=Ref.model_validate(row.instance_ref),
                )
            )
    return items


async def read_activity(
    db: AsyncConnection, scope: UUID, reference: Ref, before: int | None
) -> ToolResult:
    """Read only records already presented in the fixed learning space."""
    if reference.type == "activity_history":
        boundary = int(reference.path.removeprefix("/")) if reference.path else 0
        if before is not None and before >= boundary:
            return unavailable()
        rows = (
            await db.execute(
                text("""
            SELECT m.message_id,m.role,m.parts,m.message_seq
            FROM interaction.messages m JOIN interaction.message_assignments a USING(message_id)
            WHERE m.scope_id=:scope AND a.activity_id=:id
              AND m.role IN ('student','assistant') AND m.message_seq<:before
            ORDER BY m.message_seq DESC LIMIT :limit
        """),
                {
                    "scope": scope,
                    "id": UUID(reference.id),
                    "before": before or boundary,
                    "limit": PAGE_SIZE + 1,
                },
            )
        ).all()
        selected: list[JsonValue] = []
        refs: list[Ref] = [reference]
        for row in rows[:PAGE_SIZE]:
            message = Ref(owner="interaction", type="message", id=str(row.message_id))
            entry: dict[str, JsonValue] = {"role": row.role, "parts": row.parts}
            next_before = row.message_seq
            data: dict[str, JsonValue] = {
                "messages": [entry, *selected],
                "next_before": next_before,
            }
            if "omission" in result(data, [*refs, message]).data:
                if not selected:
                    return result(
                        {
                            "omission": "该条原文过长，请指明要核对的段落。",
                            "next_before": next_before,
                        },
                        [reference, message],
                    )
                break
            selected.insert(0, entry)
            refs.append(message)
        return result(
            {
                "messages": selected,
                "next_before": rows[len(selected) - 1].message_seq
                if selected and len(rows) > len(selected)
                else None,
            },
            refs,
        )
    if before is not None:
        return unavailable()
    params = {"scope": scope, "id": UUID(reference.id)}
    if reference.type == "task_use":
        statement = await db.scalar(
            text(
                "SELECT statement FROM interaction.task_uses WHERE scope_id=:scope "
                "AND task_use_id=:id AND provided_message_ref IS NOT NULL"
            ),
            params,
        )
        return (
            result({"statement": statement}, [reference])
            if statement is not None
            else unavailable()
        )
    if reference.type == "help":
        rows = (
            await db.execute(
                text("""
            SELECT m.message_id,m.parts FROM interaction.help_facts h JOIN interaction.messages m
              ON m.scope_id=h.scope_id AND m.message_id::text=h.provided_part_refs->0->>'id'
            WHERE h.scope_id=:scope AND h.help_id=:id AND h.stage='provided'
        """),
                params,
            )
        ).one_or_none()
        if rows is None:
            return unavailable()
        return result(
            {"parts": rows.parts},
            [reference, Ref(owner="interaction", type="message", id=str(rows.message_id))],
        )
    parts = await db.scalar(
        text(
            "SELECT parts FROM interaction.messages WHERE scope_id=:scope AND message_id=:id "
            "AND role IN ('student','assistant')"
        ),
        params,
    )
    return result({"parts": parts}, [reference]) if parts is not None else unavailable()


async def read_scope(db: AsyncConnection, handle: CallHandle) -> tuple[UUID, UUID] | None:
    """Use the active execution's owner and the current detection state at read time."""
    if handle.input.step_key not in {"reply", "post_detection_help"}:
        return None
    work = await store.load(db, handle.input.run.execution_id)
    current = await history.current(db, work.scope_id)
    if current.current_round is not None and current.current_round.state == "open":
        return None
    if handle.input.step_key == "post_detection_help" and (
        current.current_round is None or current.current_round.state != "closed"
    ):
        return None
    authorization = await store.authorization(db, work.execution_id)
    return work.scope_id, UUID(authorization.basis_refs[0].id)
