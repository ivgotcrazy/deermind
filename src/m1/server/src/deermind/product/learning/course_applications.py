"""Confirm an immutable course check with the related space adoptions."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, FactRecord, ProducerAccess, Ref
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.learning import course_facts as facts
from deermind.product.learning.course_checks import CourseChecks
from deermind.product.learning.course_spaces import CourseSpaces
from deermind.product.persistence.receipts import (
    claim_request,
    complete_request,
    find_completed_request,
)
from deermind.product.public.courses import (
    CONFIRM_COURSE,
    CourseApplyReceipt,
    CourseApplyResult,
    CourseConfirmCommand,
    CourseSnapshot,
)
from pydantic import JsonValue, TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


def normalized_basis(snapshot: CourseSnapshot) -> dict[str, JsonValue]:
    items: list[dict[str, object]] = []
    for item in sorted(snapshot.items, key=lambda i: i.item_id):
        methods: list[dict[str, object]] = []
        for method in sorted(
            item.methods, key=lambda m: (m.method_ref.object_id, m.method_ref.version)
        ):
            methods.append(
                {
                    "method_ref": method.method_ref.model_dump(mode="json"),
                    "chapter_refs": sorted(map(str, method.chapter_refs)),
                    "aspects": [
                        aspect.model_dump(mode="json")
                        for aspect in sorted(method.aspects, key=lambda a: a.aspect_ref.aspect_code)
                    ],
                }
            )
        items.append(
            {
                "item_id": str(item.item_id),
                "claim_ref": item.claim_ref.model_dump(mode="json"),
                "chapter_refs": sorted(map(str, item.chapter_refs)),
                "task_conditions": item.task_conditions.model_dump(mode="json"),
                "method_mode": item.method_mode,
                "methods": methods,
            }
        )
    chapter_ids = {identity for item in snapshot.items for identity in item.chapter_refs}
    data = {
        "items": items,
        "allowed_methods": [
            {
                "chapter_id": str(chapter.chapter_id),
                "associations": sorted(
                    [
                        {
                            "task": association.task_ref.model_dump(mode="json"),
                            "methods": sorted(
                                [
                                    method.model_dump(mode="json")
                                    for method in association.method_refs
                                ],
                                key=canonical_json,
                            ),
                        }
                        for association in chapter.associations
                    ],
                    key=canonical_json,
                ),
            }
            for chapter in sorted(snapshot.chapters, key=lambda c: c.chapter_id)
            if chapter.chapter_id in chapter_ids
        ],
        "evaluation_gaps": sorted(
            [gap.model_dump(mode="json") for gap in snapshot.evaluation_gaps], key=canonical_json
        ),
    }
    return TypeAdapter(dict[str, JsonValue]).validate_python(data)


class CourseApplications:
    def __init__(self, checks: CourseChecks, spaces: CourseSpaces) -> None:
        self.checks = checks
        self.spaces = spaces
        self.engine = checks.engine

    async def receipt(
        self, principal: UUID, _session: UUID, query: ReceiptQuery
    ) -> ReceiptView[CourseApplyResult]:
        async with self.engine.connect() as db:
            receipt = await find_completed_request(
                db,
                principal,
                CONFIRM_COURSE,
                query.resource_id,
                query.request_id,
            )
            if receipt is None or receipt.result_ref is None:
                return ReceiptView[CourseApplyResult](receipt_state="not_found")
            result = await self._result(db, receipt.result_ref)
        return ReceiptView[CourseApplyResult](
            receipt_state="completed",
            receipt_ref=receipt.request_ref,
            result=result,
        )

    async def _result(self, db: AsyncConnection, reference: Ref) -> CourseApplyResult:
        changed = reference.type == "course_application"
        affected: list[UUID] = (
            list(
                (
                    await db.scalars(
                        text(
                            "SELECT space_id FROM product.space_adoption WHERE application_ref=:id "
                            "AND reason='course_application' ORDER BY space_id"
                        ),
                        {"id": UUID(reference.id)},
                    )
                ).all()
            )
            if changed
            else []
        )
        return CourseApplyResult(
            application_ref=facts.ref("course_application", UUID(reference.id)),
            changed=changed,
            affected_spaces=affected,
        )

    async def _basis(
        self, db: AsyncConnection, snapshot: CourseSnapshot, textbook: UUID, now: datetime
    ) -> tuple[UUID, facts.BasisRow | None]:
        normalized = normalized_basis(snapshot)
        digest = sha256(canonical_json(normalized).encode()).hexdigest()
        raw = (
            await db.execute(
                text(
                    "SELECT basis_id,normalized_basis FROM product.target_basis WHERE "
                    "textbook_id=:book "
                    "AND target_id=:target AND digest=:digest"
                ),
                {"book": textbook, "target": snapshot.target_ref.target_id, "digest": digest},
            )
        ).one_or_none()
        if raw is None:
            row = facts.BasisRow(
                basis_id=uuid4(),
                textbook_id=textbook,
                target_id=snapshot.target_ref.target_id,
                normalized_basis=normalized,
                digest=digest,
                created_at=now,
            )
            return row.basis_id, row
        if canonical_json(raw.normalized_basis) != canonical_json(normalized):
            raise RuntimeError("Target basis digest collision")
        return raw.basis_id, None

    async def confirm(self, principal: UUID, command: CourseConfirmCommand) -> CourseApplyReceipt:
        request, commit = uuid4(), uuid4()
        normalized = command.model_dump(mode="json")
        async with self.engine.connect() as db:
            check = await self.checks.fixed_check(db, command.check_ref)
            textbook = check.input.textbook_id
            saved = await find_completed_request(
                db, principal, CONFIRM_COURSE, textbook, command.request_id, normalized
            )
            if saved is not None and saved.result_ref is not None:
                return CourseApplyReceipt(
                    request_ref=saved.request_ref, result=await self._result(db, saved.result_ref)
                )
            if command.expected_application_ref != check.base_application_ref:
                raise RequestError(409, "check_stale", "检查基准与确认请求不一致。")
            if check.blockers:
                raise RequestError(
                    409, "not_ready", "课程还有阻止应用的项目。", issues=check.blockers
                )
            previous = await self.checks.validate_base(db, check.input)
            snapshot = check.proposed_application
            now = datetime.now(UTC)
            basis_id, basis_row = await self._basis(db, snapshot, textbook, now)

        actor = facts.ref("account", principal)
        course = facts.CourseRow(
            application_id=uuid4(),
            textbook_id=textbook,
            target_id=snapshot.target_ref.target_id,
            previous_application_id=previous.application_id if previous else None,
            check_ref=check.check_id,
            content_snapshot=snapshot,
            target_basis_ref=basis_id,
            actor_ref=actor,
            created_at=now,
        )
        reference = facts.ref("course_application", course.application_id)
        records: list[FactRecord] = []
        if basis_row is not None:
            records.append(facts.record(facts.BASIS, basis_id, basis_row))
        records.append(facts.record(facts.COURSE, course.application_id, course))
        scope = ("course_application", textbook)
        applied = facts.event(
            facts.APPLIED,
            scope,
            reference,
            facts.CourseApplied(
                application_ref=reference,
                previous_application_ref=check.base_application_ref,
                check_ref=command.check_ref,
                textbook_id=textbook,
                target_ref=snapshot.target_ref,
                request_ref=request,
                records=records,
            ),
            request_id=command.request_id,
        )
        access = ProducerAccess("product", actor, frozenset({scope}))
        events = self.checks.materials.events
        prepared = await self.checks.materials.attachments.prepare(events, access, (applied,))

        async with self.engine.begin() as db:
            receipt = await claim_request(
                db,
                principal_id=str(principal),
                action=CONFIRM_COURSE,
                scope_id=str(textbook),
                request_id=command.request_id,
                normalized_input=normalized,
                reserved_ref=request,
            )
            if receipt.result_ref is not None:
                return CourseApplyReceipt(
                    request_ref=receipt.request_ref,
                    result=await self._result(db, receipt.result_ref),
                )
            import_id, domain, title = await self.checks.book(db, textbook, lock=True)
            previous = await self.checks.validate_base(db, check.input)
            selected = await self.checks.selections(db, textbook, import_id, check.input)
            if title != snapshot.textbook_title or any(
                chapter not in snapshot.chapters for chapter in selected
            ):
                raise RequestError(409, "check_stale", "已选用的教材内容发生变化，请重新检查。")
            for chapter in snapshot.chapters:
                for row in chapter.associations:
                    try:
                        await self.checks.check_methods(db, domain, row.task_ref, row.method_refs)
                    except RequestError as error:
                        if error.code in {"invalid_reference", "not_found"}:
                            raise RequestError(
                                409, "check_stale", "课程引用的领域定义已变化。"
                            ) from error
                        raise
            if previous is not None and previous.content_snapshot == snapshot:
                same = facts.ref("course_application_no_change", previous.application_id)
                await complete_request(db, receipt, same)
                return CourseApplyReceipt(request_ref=request, result=await self._result(db, same))

            spaces: list[UUID] = list(
                (
                    await db.scalars(
                        text(
                            "SELECT space_id FROM product.learning_space WHERE textbook_id=:book "
                            "AND target_id=:target ORDER BY space_id FOR UPDATE"
                        ),
                        {"book": textbook, "target": course.target_id},
                    )
                ).all()
            )
            drafts: list[EventDraft] = []
            for space_id in spaces:
                space = await self.spaces.row(db, space_id)
                adoption = await self.spaces.adoption(db, space.current_adoption_ref)
                _updated, changes = self.spaces.build_adoption(
                    space, course, adoption, now, command.request_id
                )
                drafts.extend(changes)
            sequence = await lock_scope_sequence(db, *scope)
            (result,) = await events.append(
                db,
                access,
                prepared,
                commit_id=commit,
                correlation_id=request,
                expected_seq={scope: sequence},
            )
            await facts.project(db, result)
            if drafts:
                await self.spaces.append(db, principal, request, drafts, commit_id=commit)
            await complete_request(db, receipt, reference)
        return CourseApplyReceipt(
            request_ref=request,
            result=CourseApplyResult(
                application_ref=reference, changed=True, affected_spaces=spaces
            ),
        )
