"""按业务入口确定的范围读取事件。查询元数据、定点取材、连续回放各用一个入口。"""

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
    def __init__(
        self, engine: AsyncEngine, files: FileStorage, registrations: Sequence[EventRegistration]
    ) -> None:
        self.engine = engine
        self.files = files
        self._events = {(r.event_type, r.schema_version): r for r in registrations}
        if len(self._events) != len(registrations):
            raise ValueError("Duplicate event schema")

    @staticmethod
    def _limit(limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= PAGE_MAX:
            raise ValueError("Page limit must be between 1 and 100")

    @staticmethod
    def _response(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
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
        for date in (filters.recorded_from, filters.recorded_to):
            if date is not None and date.utcoffset() is None:
                raise ValueError("Filter timestamps must include timezone")
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
        if filters.event_types:
            clauses.append("event_type=ANY(:types)")
            parameters["types"] = list(filters.event_types)
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
        registration = self._events.get((event.event_type, event.schema_version))
        if (
            registration is None
            or registration.producer != event.producer
            or registration.scope_kind != event.scope_kind
        ):
            raise ValueError("Stored event does not match its registration")
        payload = registration.payload_model.model_validate_json(canonical_json(event.payload))
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
        model = registration.record_models.get((record.record_type, record.schema_version))
        if model is None:
            raise ValueError("Fact record schema is not registered")
        if isinstance(record.content, InlineContent):
            content = record.content.value
            encoded = canonical_json(content).encode()
        else:
            reference = record.content
            row = await connection.scalar(
                text("SELECT to_jsonb(f) FROM runtime.file_objects f WHERE file_id=:id"),
                {"id": reference.file_id},
            )
            if row is None:
                raise OSError("Fact attachment registration is missing")
            file = FileObject.model_validate_json(canonical_json(row))
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
            if canonical_json(content).encode() != encoded:
                raise ValueError("Fact attachment is not canonically encoded")
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
        for column, value in (
            ("event_type", expected_event_type),
            ("schema_version", schema_version),
            ("correlation_id", correlation_id),
        ):
            if value is not None:
                clauses.append(f"{column}=:{column}")
                params[column] = value
        selectors: list[tuple[EventPartRef, list[str]]] = []
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
            if raw is None:
                raise LookupError("No event matches the requested scope and conditions")
            event = EventFact.model_validate_json(canonical_json(raw))
            registration, payload = self._decode(event)
            records = {r.record_id: r for r in payload.records}
            items: list[JsonValue] = []
            budget = FACT_READ_LIMIT
            for ref, parts in selectors:
                schema: dict[str, JsonValue]
                if ref.record_id is None:
                    content = {k: v for k, v in event.payload.items() if k != "records"}
                    consumed = len(canonical_json(content).encode())
                    schema = {
                        "event_type": event.event_type,
                        "schema_version": event.schema_version,
                    }
                else:
                    record = records.get(ref.record_id)
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
                if budget < 0:
                    raise ValueError("Fact reading exceeds the 32MiB budget")
                missing = False
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
        if (
            type(after_seq) is not int
            or type(upper_seq) is not int
            or not 0 <= after_seq <= upper_seq
        ):
            raise ValueError("Invalid scan bounds")
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
        for seq, raw in rows:
            if seq != scanned + 1:
                raise ValueError("A source sequence is missing")
            scanned = seq
            if raw is not None:
                event = EventFact.model_validate_json(canonical_json(raw))
                stored, consumed = await self._restore(connection, event, budget)
                events.append(stored)
                budget -= consumed
        if scanned != end:
            raise ValueError("A source sequence is missing")
        return ScanPage(tuple(events), scanned, upper_seq)

    async def _restore(
        self, connection: AsyncConnection, event: EventFact, budget: int
    ) -> tuple[StoredEvent, int]:
        registration, wire = self._decode(event)
        body = {k: v for k, v in event.payload.items() if k != "records"}
        consumed = len(canonical_json(body).encode())
        if consumed > budget:
            raise ValueError("Fact reading exceeds the 32MiB budget")
        records: list[JsonValue] = []
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
