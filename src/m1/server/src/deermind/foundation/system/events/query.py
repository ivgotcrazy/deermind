"""按业务入口确定的范围读取事件。查询元数据、定点取材、连续回放各用一个入口。

分层定位：foundation（公共运行底座 / 事件读取）
对外契约：EventReader 提供元数据分页、定点片段取材与范围连续回放三类只读入口。
边界约束：读取范围由调用方在业务层授权后传入；附件读取按摘要与登记身份核验，并受读取预算约束。
"""

import asyncio
import hashlib
from collections.abc import Sequence
from contextlib import nullcontext
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import (
    FACT_READ_LIMIT,
    PAGE_DEFAULT,
    PAGE_MAX,
    RESPONSE_LIMIT,
    EventFact,
    EventFilter,
    EventPartRef,
    ScanPage,
    fragment,
    pointer_parts,
)
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactRecord,
    InlineContent,
    StoredEvent,
)
from deermind.abstractions.file_records import FileObject
from deermind.abstractions.files import FileStorage
from pydantic import JsonValue, TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


class EventReader:
    """事件只读入口：持有文件存储与事件登记，负责元数据查询、片段取材与回放恢复。"""

    def __init__(
        self, engine: AsyncEngine, files: FileStorage, registrations: Sequence[EventRegistration]
    ) -> None:
        self.engine = engine
        self.files = files
        self._events = {(r.event_type, r.schema_version): r for r in registrations}
        # 同类型同版本重复登记会互相覆盖，判重复 schema。
        if len(self._events) != len(registrations):
            raise ValueError("Duplicate event schema")

    @staticmethod
    def _limit(limit: int) -> None:
        """校验分页/片段数量落在允许区间内。"""
        # 必须是整数且在 1 到单页上限之间，拒绝越界分页。
        if type(limit) is not int or not 1 <= limit <= PAGE_MAX:
            raise ValueError("Page limit must be between 1 and 100")

    @staticmethod
    def _response(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """校验响应整体不超过响应体积上限。"""
        # 规范化编码后字节数超响应上限，提示调用方收窄范围。
        if len(canonical_json(value).encode()) > RESPONSE_LIMIT:
            raise ValueError("Response exceeds 4MiB; request a smaller range")
        return value

    async def query_metadata(
        self,
        scope_kind: str,
        scope_id: UUID,
        *,
        filters: EventFilter | None = None,
        after_seq: int = 0,
        upper_seq: int | None = None,
        limit: int = PAGE_DEFAULT,
        connection: AsyncConnection | None = None,
    ) -> dict[str, JsonValue]:
        """列表只取元数据；后续页沿用第一页的上界。"""
        self._limit(limit)
        filters = filters or EventFilter()
        # 时间过滤条件必须带时区，避免按本地时间错配。
        for date in (filters.recorded_from, filters.recorded_to):
            if date is not None and date.utcoffset() is None:
                raise ValueError("Filter timestamps must include timezone")
        # 起止区间方向非法（起 ≥ 止）时拒绝。
        if (
            filters.recorded_from is not None
            and filters.recorded_to is not None
            and filters.recorded_from >= filters.recorded_to
        ):
            raise ValueError("Invalid recorded time interval")
        clauses = [
            "scope_kind=:kind",
            "scope_id=:scope",
            "scope_event_seq>:after",
            "scope_event_seq<=:upper",
        ]
        parameters: dict[str, object] = {
            "kind": scope_kind,
            "scope": scope_id,
            "after": after_seq,
            "limit": limit + 1,
        }
        # 指定类型时追加类型过滤。
        if filters.event_types:
            clauses.append("event_type=ANY(:types)")
            parameters["types"] = list(filters.event_types)
        # 逐项拼接可选等值/区间条件，仅在对应过滤值存在时加入 WHERE。
        for column, value, expression in (
            ("id", filters.event_id, "event_id=:id"),
            ("correlation", filters.correlation_id, "correlation_id=:correlation"),
            ("cause", filters.causation_event_id, "causation_event_id=:cause"),
            ("from", filters.recorded_from, "recorded_at>=:from"),
            ("to", filters.recorded_to, "recorded_at<:to"),
        ):
            if value is not None:
                clauses.append(expression)
                parameters[column] = value
        # 按主体引用过滤：命中主体列表或所有者引用其一即可。
        if filters.subject_ref is not None:
            clauses.append(
                "(subject_refs @> CAST(:subject AS jsonb) OR owner_ref=CAST(:owner AS jsonb))"
            )
            owner = filters.subject_ref.model_dump(mode="json", exclude_none=True)
            parameters.update(subject=canonical_json([owner]), owner=canonical_json(owner))
        async with self.engine.connect() if connection is None else nullcontext(connection) as db:
            current = (
                await db.scalar(
                    text(
                        "SELECT last_seq FROM runtime.scope_event_heads "
                        "WHERE scope_kind=:kind AND scope_id=:scope"
                    ),
                    parameters,
                )
                or 0
            )
            upper = current if upper_seq is None else upper_seq
            # 起止序号必须为整数且落在 [0, 当前最大序号] 区间内。
            if (
                type(after_seq) is not int
                or type(upper) is not int
                or not 0 <= after_seq <= upper <= current
            ):
                raise ValueError("Invalid query bounds")
            parameters["upper"] = upper
            statement = (
                "SELECT event_id, event_type, schema_version, scope_kind, scope_id, "
                "scope_event_seq, occurred_at, recorded_at, time_basis, owner_ref, subject_refs "
                "FROM runtime.events WHERE "
                + " AND ".join(clauses)
                + " ORDER BY scope_event_seq LIMIT :limit"
            )
            # 多取一条以判断是否还有下一页，返回时裁回 limit 条。
            rows = (
                await db.scalars(text("SELECT to_jsonb(m) FROM (" + statement + ") m"), parameters)
            ).all()
        return self._response(
            {
                "items": list(rows[:limit]),
                "upper_seq": upper,
                "next_after_seq": rows[limit - 1]["scope_event_seq"] if len(rows) > limit else None,
            }
        )

    def _decode(self, event: EventFact) -> tuple[EventRegistration, EventPayload]:
        """按事件类型与版本找回登记，核对生产者与范围后严格解码正文。"""
        registration = self._events.get((event.event_type, event.schema_version))
        # 登记缺失，或生产者/范围类型与登记不符，视为落库事件被篡改。
        if (
            registration is None
            or registration.producer != event.producer
            or registration.scope_kind != event.scope_kind
        ):
            raise ValueError("Stored event does not match its registration")
        payload = registration.payload_model.model_validate_json(canonical_json(event.payload))
        # 同一正文内出现重复记录编号，归属不唯一，拒绝解码。
        if len({r.record_id for r in payload.records}) != len(payload.records):
            raise ValueError("Ambiguous fact record")
        return registration, payload

    async def _body(
        self,
        connection: AsyncConnection,
        event: EventFact,
        registration: EventRegistration,
        record: FactRecord,
        budget: int,
    ) -> tuple[dict[str, JsonValue], int]:
        """展开单条事实记录：内联直接解码，外置附件核验身份与摘要后读取，并返回占用字节数。"""
        model = registration.record_models.get((record.record_type, record.schema_version))
        # 记录类型与版本未登记，无法按 Schema 校验，拒绝展开。
        if model is None:
            raise ValueError("Fact record schema is not registered")
        # 内联内容直接取正文；外置附件须先核验登记身份与摘要再读取。
        if isinstance(record.content, InlineContent):
            content = record.content.value
            encoded = canonical_json(content).encode()
        else:
            reference = record.content
            row = await connection.scalar(
                text("SELECT to_jsonb(f) FROM runtime.file_objects f WHERE file_id=:id"),
                {"id": reference.file_id},
            )
            # 附件登记缺失，无法证明其归属。
            if row is None:
                raise OSError("Fact attachment registration is missing")
            file = FileObject.model_validate_json(canonical_json(row))
            # 后端、摘要、类型、类别、取材键任一不符，即身份或完整性元数据被改动。
            if (
                file.backend != self.files.backend
                or file.sha256 != reference.sha256
                or file.media_type != reference.media_type
                or file.category != "fact"
                or file.artifact_key != f"fact:{event.event_id}:{record.record_id}"
            ):
                raise OSError("Fact attachment identity or integrity metadata differs")
            encoded = await asyncio.to_thread(self.files.read, file.bytes_ref(), max_bytes=budget)
            content = JSON_OBJECT.validate_json(encoded, strict=True)
            # 回读内容规范化编码后与原字节不一致，说明非规范编码或被改写。
            if canonical_json(content).encode() != encoded:
                raise ValueError("Fact attachment is not canonically encoded")
        # 单条记录占用超读取预算即拒绝。
        if len(encoded) > budget:
            raise ValueError("Fact reading exceeds the 32MiB budget")
        model.model_validate_json(encoded)
        return content, len(encoded)

    async def read_facts(
        self,
        scope_kind: str,
        scope_id: UUID,
        event_id: UUID,
        *,
        refs: Sequence[EventPartRef],
        expected_event_type: str | None = None,
        schema_version: int | None = None,
        correlation_id: UUID | None = None,
    ) -> dict[str, JsonValue]:
        """只展开调用方点名的片段。空路径显式选择整条记录或全部动作字段。"""
        self._limit(len(refs))
        clauses = ["event_id=:id", "scope_kind=:kind", "scope_id=:scope"]
        params: dict[str, object] = {"id": event_id, "kind": scope_kind, "scope": scope_id}
        # 逐项追加可选类型/版本/关联键过滤。
        for column, value in (
            ("event_type", expected_event_type),
            ("schema_version", schema_version),
            ("correlation_id", correlation_id),
        ):
            if value is not None:
                clauses.append(f"{column}=:{column}")
                params[column] = value
        selectors: list[tuple[EventPartRef, list[str]]] = []
        # 解析每个片段指针路径，并校验其归属到本次事件。
        for ref in refs:
            parts = pointer_parts(ref.path)
            if ref.event_id != event_id or (ref.record_id is None and parts[:1] == ["records"]):
                raise ValueError("Invalid event or action selector")
            selectors.append((ref, parts))
        async with self.engine.connect() as connection:
            raw = await connection.scalar(
                text("SELECT to_jsonb(e) FROM runtime.events e WHERE " + " AND ".join(clauses)),
                params,
            )
            # 范围与条件下无匹配事件，拒绝取材。
            if raw is None:
                raise LookupError("No event matches the requested scope and conditions")
            event = EventFact.model_validate_json(canonical_json(raw))
            registration, payload = self._decode(event)
            records = {r.record_id: r for r in payload.records}
            items: list[JsonValue] = []
            budget = FACT_READ_LIMIT
            # 逐条展开调用方点名的片段，累计占用读取预算。
            for ref, parts in selectors:
                schema: dict[str, JsonValue]
                # 未指定记录编号：取整条事件正文（不含 records 列表）。
                if ref.record_id is None:
                    content = {k: v for k, v in event.payload.items() if k != "records"}
                    consumed = len(canonical_json(content).encode())
                    schema = {
                        "event_type": event.event_type,
                        "schema_version": event.schema_version,
                    }
                else:
                    record = records.get(ref.record_id)
                    # 点名的记录编号在正文中不存在。
                    if record is None:
                        raise ValueError("Fact record is missing")
                    content, consumed = await self._body(
                        connection, event, registration, record, budget
                    )
                    schema = {
                        "record_type": record.record_type,
                        "schema_version": record.schema_version,
                    }
                budget -= consumed
                # 累计占用超预算即停止取材。
                if budget < 0:
                    raise ValueError("Fact reading exceeds the 32MiB budget")
                missing = False
                # 按指针路径取片段；路径不存在时记为缺失字段，不抛错中断。
                try:
                    value = fragment(content, parts)
                except (KeyError, IndexError):
                    value = None
                    missing = True
                items.append(
                    {
                        "ref": ref.model_dump(mode="json"),
                        "schema_ref": schema,
                        "content": value,
                        "sha256": hashlib.sha256(canonical_json(value).encode()).hexdigest(),
                        "visible_paths": [ref.path],
                        "visibility": "partial" if parts else "complete",
                        "completeness": "incomplete" if missing else "complete",
                        "missing_reasons": ["field_missing"] if missing else [],
                    }
                )
                self._response({"items": items})
        return {"items": items}

    async def scan_scope(
        self,
        connection: AsyncConnection,
        scope_kind: str,
        scope_id: UUID,
        *,
        after_seq: int,
        upper_seq: int,
        types: frozenset[str],
        limit: int = PAGE_DEFAULT,
    ) -> ScanPage:
        """在调用方事务内证明整页连续。只为投影器选中的类型读取完整信封。"""
        self._limit(limit)
        # 扫描起止序号必须为整数且起 ≤ 止。
        if (
            type(after_seq) is not int
            or type(upper_seq) is not int
            or not 0 <= after_seq <= upper_seq
        ):
            raise ValueError("Invalid scan bounds")
        # 本页终点取步长与上界的较小值。
        end = min(after_seq + limit, upper_seq)
        rows = await connection.execute(
            text(
                "SELECT scope_event_seq, CASE WHEN event_type=ANY(:types) THEN to_jsonb(e) END "
                "FROM runtime.events e WHERE scope_kind=:kind AND scope_id=:scope "
                "AND scope_event_seq>:after AND scope_event_seq<=:end ORDER BY scope_event_seq"
            ),
            {
                "types": list(types),
                "kind": scope_kind,
                "scope": scope_id,
                "after": after_seq,
                "end": end,
            },
        )
        events: list[StoredEvent] = []
        scanned = after_seq
        budget = FACT_READ_LIMIT
        # 按序号逐条回放；序号不连续即证明事件流有缺口，中止投影。
        for seq, raw in rows:
            if seq != scanned + 1:
                raise ValueError("A source sequence is missing")
            scanned = seq
            # 仅投影器选中的类型取完整信封，其余类型只占用序号占位。
            if raw is not None:
                event = EventFact.model_validate_json(canonical_json(raw))
                stored, consumed = await self._restore(connection, event, budget)
                events.append(stored)
                budget -= consumed
        # 页末仍未扫到终点，说明尾部序号缺失。
        if scanned != end:
            raise ValueError("A source sequence is missing")
        return ScanPage(tuple(events), scanned, upper_seq)

    async def _restore(
        self, connection: AsyncConnection, event: EventFact, budget: int
    ) -> tuple[StoredEvent, int]:
        """回放时把落库事件连同外置附件恢复为完整 StoredEvent，并返回已占用字节数。"""
        registration, wire = self._decode(event)
        body = {k: v for k, v in event.payload.items() if k != "records"}
        consumed = len(canonical_json(body).encode())
        # 事件主正文已超预算，不再展开外置记录。
        if consumed > budget:
            raise ValueError("Fact reading exceeds the 32MiB budget")
        records: list[JsonValue] = []
        # 逐条把外置附件恢复为内联内容，并累计占用字节。
        for record in wire.records:
            content, size = await self._body(
                connection, event, registration, record, budget - consumed
            )
            consumed += size
            restored = record.model_copy(
                update={"content": InlineContent(storage="inline", value=content)}
            )
            records.append(restored.model_dump(mode="json"))
        body["records"] = records
        draft = EventDraft(
            event_id=event.event_id,
            event_type=event.event_type,
            schema_version=event.schema_version,
            scope_kind=event.scope_kind,
            scope_id=event.scope_id,
            owner_ref=event.owner_ref,
            payload=body,
            source_request_id=event.source_request_id,
            causation_event_id=event.causation_event_id,
            subject_refs=tuple(event.subject_refs),
            source_execution_ref=event.source_execution_ref,
        )
        payload = registration.payload_model.model_validate_json(canonical_json(body))
        registration.validate(draft, payload)
        return StoredEvent(
            draft,
            event.commit_id,
            event.correlation_id,
            event.scope_event_seq,
            event.recorded_at,
            payload,
        ), consumed
