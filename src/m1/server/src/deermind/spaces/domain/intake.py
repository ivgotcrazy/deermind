"""Domain 消费已登记的教材提交，原子保存受理事实及业务待办。"""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal
from uuid import UUID, uuid4

from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from deermind.abstractions.delivery import Acceptance, EventNotice
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventFilter, EventPartRef
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    FactRecord,
    InlineContent,
    ProducerAccess,
    Ref,
    StoredEvent,
)
from deermind.abstractions.material_intake import (
    DELETED,
    RECEIVED,
    REJECTED,
    REQUESTED,
    CandidateKey,
    IntakeDecided,
    IntakeRequested,
    IntakeSource,
)
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore, lock_scope_sequence
from deermind.foundation.system.public.errors import RequestError
from deermind.spaces.domain.public import IntakeDetail, IntakeKind, IntakeList, IntakeView

ARTIFACT = "domain.artifact"
ITEM = "domain.intake_item"
SUBMISSION = "domain.intake_submission"


class InputArtifact(FactModel):
    artifact_id: UUID
    domain_id: UUID
    kind: Literal["input"] = "input"
    input_ref: Ref
    definition_refs: list[Ref]
    payload: dict[str, JsonValue]
    rule_ref: Ref | None = None
    model_call_ref: Ref | None = None
    command_ref: Ref | None = None
    created_at: datetime


class IntakeItem(FactModel):
    item_id: UUID
    domain_id: UUID
    candidate_key: str
    source_ref: IntakeSource
    input_artifact_id: UUID
    kind: IntakeKind
    title: str
    group_id: UUID
    parent_item_id: UUID | None
    parent_instance_ref: Ref | None
    state: Literal["pending", "completed", "removed"] = "pending"
    revision: int = 1
    result_ref: Ref | None = None
    processed_request_ref: UUID | None = None
    created_at: datetime

    def reference(self) -> Ref:
        return Ref(owner="domain", type="intake_item", id=str(self.item_id), revision=self.revision)

    def view(self) -> IntakeView:
        parent = self.parent_instance_ref
        if self.parent_item_id is not None:
            # 挂在父待办下时，父引用展示为待办条目；否则展示实例引用。
            parent = Ref(owner="domain", type="intake_item", id=str(self.parent_item_id))
        return IntakeView(
            item_ref=self.reference(),
            kind=self.kind,
            title=self.title,
            state=self.state,
            parent_ref=parent,
            result_ref=self.result_ref,
        )


class IntakeSubmission(FactModel):
    submission_id: UUID
    trigger_event_id: UUID
    domain_id: UUID
    product_submission_ref: Ref
    input_artifact_id: UUID
    outcome: Literal["received", "rejected"]
    item_refs: list[Ref]
    issues: list[dict[str, str]]
    decision_event_id: UUID
    created_at: datetime


_MODELS = {ARTIFACT: InputArtifact, ITEM: IntakeItem, SUBMISSION: IntakeSubmission}


def _record(kind: str, identity: UUID, value: FactModel) -> FactRecord:
    return FactRecord(
        record_id=str(identity),
        record_type=kind,
        schema_version=1,
        content=InlineContent(storage="inline", value=value.model_dump(mode="json")),
    )


def _validate(draft: EventDraft, payload: EventPayload) -> None:
    if not isinstance(payload, IntakeDecided):
        raise ValueError("Invalid domain intake fact")
    kind = RECEIVED if payload.outcome == "received" else REJECTED
    if draft.event_type != kind or draft.causation_event_id != payload.trigger_event_id:
        # 事件类型与受理结论、触发事件必须一致。
        raise ValueError("Intake result does not match its source")
    counts = [item.record_type for item in payload.records]
    if counts[:2] != [ARTIFACT, SUBMISSION] or any(name != ITEM for name in counts[2:]):
        # 记录顺序固定：输入产物、提交记录，其后全是待办条目。
        raise ValueError("Invalid intake projection records")
    if payload.outcome == "rejected" and (not payload.issues or payload.items or counts[2:]):
        # 拒收必须带问题，且不得产生待办条目。
        raise ValueError("A rejected intake cannot create pending items")


REGISTRATIONS = [
    EventRegistration(
        kind,
        1,
        "domain",
        "material_import",
        IntakeDecided,
        _validate,
        {(name, 1): model for name, model in _MODELS.items()},
    )
    for kind in (RECEIVED, REJECTED)
]


async def _project(connection: AsyncConnection, event: StoredEvent) -> None:
    for record in event.payload.records:
        relation = record.record_type
        if relation not in _MODELS or not isinstance(record.content, InlineContent):
            # 记录类型须在固定白名单内，且为内联内容。
            raise ValueError("Invalid intake record")
        content = {**record.content.value, "source_event_id": str(event.draft.event_id)}
        # 关系名只来自模块固定白名单。父题排在参考之前，外键在写入时校验。
        await connection.execute(
            text(
                f"INSERT INTO {relation} SELECT * FROM "
                f"jsonb_populate_record(NULL::{relation},CAST(:content AS jsonb))"
            ),
            {"content": canonical_json(content)},
        )


class IntakeRefused(ValueError):
    """已可信取材，但引用或业务范围不允许整批受理。"""


class DomainIntake:
    def __init__(self, engine: AsyncEngine, reader: EventReader, store: EventStore) -> None:
        self.engine = engine
        self.reader = reader
        self.store = store

    async def list_items(
        self,
        domain_id: UUID,
        kind: IntakeKind | None,
        cursor: str | None,
        limit: int,
        reader_id: UUID,
    ) -> IntakeList:
        token = sha256(f"{reader_id}:{domain_id}:{kind}".encode()).hexdigest()
        after = None
        if cursor is not None:
            # 续页游标须带本查询的读令牌前缀，防止跨列表翻页。
            prefix, _, position = cursor.partition(".")
            try:
                if prefix != token:
                    raise ValueError("Unexpected cursor")
                after = UUID(position)
            except ValueError as error:
                raise RequestError(400, "invalid_request", "待入库列表的续页位置无效。") from error
        async with self.engine.connect() as connection:
            rows = (
                await connection.scalars(
                    text(
                        "SELECT to_jsonb(i)-'source_event_id' FROM domain.intake_item i "
                        "WHERE domain_id=:domain AND state='pending' "
                        "AND (CAST(:kind AS text) IS NULL OR kind=:kind) "
                        "AND (CAST(:after AS uuid) IS NULL OR item_id>:after) "
                        "ORDER BY item_id LIMIT :limit"
                    ),
                    {"domain": domain_id, "kind": kind, "after": after, "limit": limit + 1},
                )
            ).all()
        items = [IntakeItem.model_validate_json(canonical_json(row)) for row in rows[:limit]]
        return IntakeList(
            items=[item.view() for item in items],
            read_token=token,
            # 多拉一行判断是否还有下一页。
            next_cursor=f"{token}.{items[-1].item_id}" if len(rows) > limit else None,
        )

    async def detail(self, domain_id: UUID, item_id: UUID) -> IntakeDetail:
        async with self.engine.connect() as connection:
            item = await self.item(connection, domain_id, item_id)
        return IntakeDetail(item=item.view())

    async def find_material_parent(
        self,
        domain_id: UUID,
        import_id: UUID,
        candidate_id: UUID,
        revision: int,
    ) -> IntakeDetail:
        source = f"{import_id}:{candidate_id}:{revision}:%"
        async with self.engine.connect() as connection:
            row = await connection.scalar(
                text(
                    "SELECT to_jsonb(i)-'source_event_id' FROM domain.intake_item i "
                    "WHERE domain_id=:domain AND kind='task_instance' AND state<>'removed' "
                    "AND candidate_key LIKE :source ORDER BY created_at DESC LIMIT 1"
                ),
                {"domain": domain_id, "source": source},
            )
        if row is None:
            # 未找到同来源的题目待办，解法缺少父题。
            raise RequestError(404, "missing_parent", "请先选择并提交对应题目。")
        item = IntakeItem.model_validate_json(canonical_json(row))
        return IntakeDetail(item=item.view())

    async def item(self, connection: AsyncConnection, domain_id: UUID, item_id: UUID) -> IntakeItem:
        row = await connection.scalar(
            text(
                "SELECT to_jsonb(i)-'source_event_id' FROM domain.intake_item i "
                "WHERE domain_id=:domain AND item_id=:item"
            ),
            {"domain": domain_id, "item": item_id},
        )
        if row is None:
            # 待办条目不存在或不属于本领域。
            raise RequestError(404, "not_found", "找不到此领域的待入库内容。")
        return IntakeItem.model_validate_json(canonical_json(row))

    async def candidate(self, item: IntakeItem) -> dict[str, JsonValue]:
        """从固定事件读取，不反查教材候选投影。"""
        scope_id = UUID(item.candidate_key.partition(":")[0])
        ref = item.source_ref.candidate_fact
        raw = await self.reader.read_facts(
            "material_import",
            scope_id,
            ref.event_id,
            expected_event_type="MaterialCandidatePrepared",
            refs=[ref],
        )
        parts = raw["items"]
        assert isinstance(parts, list) and isinstance(parts[0], dict)
        part = parts[0]["content"]
        if not isinstance(part, dict):
            # 候选事实正文须为对象结构。
            raise ValueError("Missing candidate record")
        return part

    async def _part(
        self, notice: EventNotice, reference: EventPartRef, event_type: str
    ) -> dict[str, JsonValue]:
        raw = await self.reader.read_facts(
            notice.scope_kind,
            notice.scope_id,
            reference.event_id,
            expected_event_type=event_type,
            refs=[reference],
        )
        parts = raw["items"]
        assert isinstance(parts, list) and isinstance(parts[0], dict)
        part = parts[0]["content"]
        if not isinstance(part, dict):
            raise ValueError("Intake source is not an object")
        return part

    async def _items(
        self,
        connection: AsyncConnection,
        notice: EventNotice,
        request: IntakeRequested,
        artifact_id: UUID,
        created: datetime,
    ) -> tuple[list[Ref], list[IntakeItem]]:
        existing: dict[CandidateKey, IntakeItem] = {}
        new: dict[CandidateKey, IntakeItem] = {}
        bindings = {binding.candidate_ref.key(): binding for binding in request.parent_bindings}
        sources: list[tuple[IntakeSource, IntakeKind, str, Ref | None]] = []
        for source in request.sources:
            ref = source.candidate_ref
            raw = await self._part(notice, source.candidate_fact, "MaterialCandidatePrepared")
            if (
                raw["candidate_id"] != str(ref.candidate_id)
                or raw["candidate_revision"] != ref.candidate_revision
                or raw["basis_revision"] != ref.basis_revision
                or raw["import_id"] != str(notice.scope_id)
            ):
                # 候选身份与固定事实不符，防止引用错位。
                raise ValueError("Intake candidate identity differs from its fixed fact")
            kind = raw["kind"]
            if kind not in ("kc", "task_instance", "reference"):
                # 领域只接受知识、题目、解法三类内容。
                raise IntakeRefused("领域不接受该内容类别。")
            body = raw["body"]
            if not isinstance(body, dict) or not isinstance(body.get("title"), str):
                raise ValueError("Intake candidate title is missing")
            parent = raw["parent_ref"]
            sources.append(
                (
                    source,
                    kind,
                    str(body["title"]),
                    Ref.model_validate(parent) if parent else None,
                )
            )
        sources.sort(key=lambda entry: entry[1] == "reference")
        for source, kind, title, expected_parent in sources:
            ref = source.candidate_ref
            key = (
                f"{notice.scope_id}:{ref.candidate_id}:"
                f"{ref.candidate_revision}:{source.adoption_ref.id}"
            )
            # 先查是否已存在同键待办，避免重复受理。
            saved = await connection.scalar(
                text(
                    "SELECT to_jsonb(i)-'source_event_id' FROM domain.intake_item i "
                    "WHERE domain_id=:domain AND candidate_key=:key"
                ),
                {"domain": request.domain_id, "key": key},
            )
            if saved is not None:
                # 已存在：记入既有字典，跳过新建。
                existing[ref.key()] = IntakeItem.model_validate_json(canonical_json(saved))
                continue
            parent_id: UUID | None = None
            instance: Ref | None = None
            identity = uuid4()
            group = identity
            if kind == "reference":
                # 解法须绑定到题目；分三种父题来源：新候选、已有待办、已有实例。
                binding = bindings.get(ref.key())
                if binding is None or expected_parent is None:
                    raise IntakeRefused("解法缺少对应题目。")
                parent_source = (
                    f"{notice.scope_id}:{expected_parent.id}:{expected_parent.revision}:%"
                )
                if binding.parent_candidate_ref is not None:
                    # 父题来自同批候选，在新建或既有待办中查找。
                    parent = new.get(binding.parent_candidate_ref.key()) or existing.get(
                        binding.parent_candidate_ref.key()
                    )
                    if (
                        parent is None
                        or parent.kind != "task_instance"
                        or parent.state == "removed"
                        or str(parent.source_ref.candidate_ref.candidate_id) != expected_parent.id
                        or parent.source_ref.candidate_ref.candidate_revision
                        != expected_parent.revision
                    ):
                        # 父题缺失、类别不符、已移除或候选身份不符，拒绝受理。
                        raise IntakeRefused("解法对应的题目未提交或已经移除。")
                    parent_id = parent.item_id
                    group = parent.group_id
                elif binding.parent_item_ref is not None:
                    # 父题来自既有待办条目，校验归属与固定版本。
                    parent_ref = binding.parent_item_ref
                    if parent_ref.owner != "domain" or parent_ref.type != "intake_item":
                        raise IntakeRefused("请选择同领域的待入库题目。")
                    found = (
                        await connection.execute(
                            text(
                                "SELECT item_id,group_id FROM domain.intake_item "
                                "WHERE domain_id=:domain "
                                "AND item_id=:id AND revision=:revision "
                                "AND kind='task_instance' AND state<>'removed' "
                                "AND candidate_key LIKE :source"
                            ),
                            {
                                "domain": request.domain_id,
                                "id": UUID(parent_ref.id),
                                "revision": parent_ref.revision,
                                "source": parent_source,
                            },
                        )
                    ).one_or_none()
                    if found is None:
                        # 指定版本的待办题目已不存在或被移除。
                        raise IntakeRefused("找不到固定版本的待入库题目。")
                    parent_id, group = found
                else:
                    # 父题来自已落库的题目实例，校验同领域与版本有效。
                    instance = binding.task_instance_ref
                    if (
                        instance is None
                        or instance.owner != "domain"
                        or instance.type != "task_instance"
                    ):
                        raise IntakeRefused("请选择同领域的题目实例。")
                    found = await connection.scalar(
                        text(
                            "SELECT p.group_id FROM domain.object_identity i "
                            "JOIN domain.object_version v USING(object_id) "
                            "JOIN domain.intake_item p ON p.domain_id=i.domain_id "
                            "AND p.result_ref->>'id'=i.object_id::text "
                            "WHERE i.object_id=:id AND i.domain_id=:domain "
                            "AND i.kind='task_instance' "
                            "AND v.version=:version AND NOT v.is_deleted "
                            "AND p.state='completed' AND p.candidate_key LIKE :source LIMIT 1"
                        ),
                        {
                            "id": UUID(instance.id),
                            "domain": request.domain_id,
                            "version": instance.version,
                            "source": parent_source,
                        },
                    )
                    if found is None:
                        # 实例版本已删或对应的待办未完成，拒绝绑定。
                        raise IntakeRefused("找不到固定版本的题目实例。")
                    group = found
            new[ref.key()] = IntakeItem(
                item_id=identity,
                domain_id=request.domain_id,
                candidate_key=key,
                source_ref=source,
                input_artifact_id=artifact_id,
                kind=kind,
                title=title,
                group_id=group,
                parent_item_id=parent_id,
                parent_instance_ref=instance,
                created_at=created,
            )
        items = existing | new
        return [items[ref.key()].reference() for ref in request.candidate_refs], list(new.values())

    async def receive(self, connection: AsyncConnection, notice: EventNotice) -> Acceptance:
        source = EventPartRef(event_id=notice.event_id, record_id=None, path="")
        raw = await self._part(notice, source, REQUESTED)
        request = IntakeRequested.model_validate_json(canonical_json({**raw, "records": []}))
        previous = await connection.scalar(
            text("SELECT submission_id FROM domain.intake_submission WHERE trigger_event_id=:id"),
            {"id": notice.event_id},
        )
        if previous is not None:
            # 同一触发事件已受理过，幂等返回原提交记录。
            ref = Ref(owner="domain", type="intake_submission", id=str(previous))
            return Acceptance(disposition="accepted", arrangement_refs=[ref])
        # 同领域的提交及定义保存共享根锁，防止在检查后产生重复或失效的父题引用。
        deleted = await connection.scalar(
            text(
                "SELECT v.is_deleted FROM domain.object_identity d "
                "JOIN domain.object_version v "
                "ON v.object_id=d.object_id AND v.version=d.head_version "
                "WHERE d.object_id=:id AND d.kind='domain' FOR UPDATE OF d"
            ),
            {"id": request.domain_id},
        )
        if deleted is None:
            # 领域身份不存在，提交无法归属。
            raise ValueError("Intake references a missing domain")
        created = datetime.now(UTC)
        artifact_id = uuid4()
        event_id = uuid4()
        issues: list[dict[str, str]] = []
        refs: list[Ref] = []
        items: list[IntakeItem] = []
        try:
            if deleted:
                # 领域已停用，整批拒收。
                raise IntakeRefused("所属领域已停用。")
            retired = await self.reader.query_metadata(
                "material_import",
                notice.scope_id,
                filters=EventFilter(event_types=(DELETED,)),
                limit=1,
            )
            if retired["items"]:
                # 来源教材已删除，不再受理其素材。
                raise IntakeRefused("来源教材已移除。")
            refs, items = await self._items(connection, notice, request, artifact_id, created)
        except IntakeRefused as error:
            issues = [
                {"code": "intake_rejected", "message": str(error), "path": "/parent_bindings"}
            ]
        product_ref = Ref(
            owner="product", type="material_intake_submission", id=str(request.intake_request_id)
        )
        ref = Ref(owner="domain", type="intake_submission", id=str(request.intake_request_id))
        artifact = InputArtifact(
            artifact_id=artifact_id,
            domain_id=request.domain_id,
            input_ref=product_ref,
            definition_refs=[],
            payload=raw,
            created_at=created,
        )
        result = IntakeSubmission(
            submission_id=request.intake_request_id,
            trigger_event_id=notice.event_id,
            domain_id=request.domain_id,
            product_submission_ref=product_ref,
            input_artifact_id=artifact_id,
            outcome="rejected" if issues else "received",
            item_refs=refs,
            issues=issues,
            decision_event_id=event_id,
            created_at=created,
        )
        payload = IntakeDecided(
            trigger_event_id=notice.event_id,
            domain_id=request.domain_id,
            intake_request_id=result.submission_id,
            receipt_ref=ref,
            result_ref=ref,
            outcome=result.outcome,
            items=refs,
            issues=issues,
            records=[
                _record(ARTIFACT, artifact_id, artifact),
                _record(SUBMISSION, result.submission_id, result),
                *[_record(ITEM, item.item_id, item) for item in items],
            ],
        )
        scope = (notice.scope_kind, notice.scope_id)
        sequence = await lock_scope_sequence(connection, *scope)
        (event,) = await self.store.append(
            connection,
            ProducerAccess(
                "domain",
                Ref(owner="domain", type="service", id="intake"),
                frozenset({scope}),
                frozenset({notice.event_id}),
            ),
            [
                EventDraft(
                    event_id,
                    REJECTED if issues else RECEIVED,
                    1,
                    *scope,
                    ref,
                    payload.model_dump(mode="json"),
                    None,
                    notice.event_id,
                    (product_ref,),
                )
            ],
            commit_id=uuid4(),
            correlation_id=result.submission_id,
            expected_seq={scope: sequence},
        )
        await _project(connection, event)
        return Acceptance(disposition="accepted", arrangement_refs=[ref])
