"""按登记用途读取唯一事实源；列表不透传内部信封，附件读取不绕过所有者授权。"""

import asyncio
import base64
import hashlib
import hmac
import json
from collections.abc import Sequence
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
    ReadAccess,
    ReadGrant,
    ReadHandler,
    ReadPolicy,
    fragment,
    pointer_parts,
)
from deermind.abstractions.events import EventDraft, EventRegistration, InlineContent, StoredEvent
from deermind.abstractions.file_records import FileObject
from deermind.abstractions.files import FileStorage
from pydantic import JsonValue, TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


class EventReader:
    """只读端口；cursor_key由装配层注入，跨进程须一致，不是新的读取授权。"""

    def __init__(
        self,
        engine: AsyncEngine,
        files: FileStorage,
        registrations: Sequence[EventRegistration],
        handlers: Sequence[ReadHandler],
        policies: Sequence[ReadPolicy],
        *,
        cursor_key: bytes,
    ) -> None:
        if len(cursor_key) < 32:
            raise ValueError("Cursor signing key must contain at least 32 bytes")
        self.engine = engine
        self.files = files
        self._key = cursor_key
        self._events = {(item.event_type, item.schema_version): item for item in registrations}
        self._handlers = {item.handler_id: item for item in handlers}
        self._policies = {
            (item.module, item.purpose, item.event_type, item.schema_version): item
            for item in policies
        }
        if (
            len(self._events) != len(registrations)
            or len(self._handlers) != len(handlers)
            or len(self._policies) != len(policies)
        ):
            raise ValueError("Duplicate read registration")
        for policy in policies:
            if (policy.event_type, policy.schema_version) not in self._events:
                raise ValueError("Read policy requires a registered event schema")

    def _access(self, access: ReadAccess, purpose: str | None = None) -> None:
        handler = self._handlers.get(access.handler_id)
        if (
            handler is None
            or handler.module != access.module
            or handler.purpose != access.purpose
            or (purpose is not None and purpose != handler.purpose)
            or not access.principal_id
            or not access.authorization_ref
            or not access.scopes
        ):
            raise PermissionError("Read handler or authorization context is not valid")
        if access.purpose == "projection_rebuild" and not access.maintenance_ref:
            raise PermissionError("Projection reads require a maintenance authorization")
        if access.purpose == "execution_support" and not (
            access.execution_ref or access.maintenance_ref
        ):
            raise PermissionError("Execution reads require execution or maintenance context")
        if access.purpose in {"evaluation_basis", "domain_intake"} and (
            access.source_event_ids is None or not access.resource_refs
        ):
            raise PermissionError("This handler requires explicit source and resource bounds")

    def _grant(self, access: ReadAccess, event: EventFact) -> ReadGrant:
        if (event.scope_kind, event.scope_id) not in access.scopes or (
            access.source_event_ids is not None and event.event_id not in access.source_event_ids
        ):
            raise PermissionError("Event is outside the authorized source set")
        policy = self._policies.get(
            (access.module, access.purpose, event.event_type, event.schema_version)
        )
        grant = policy.authorize(access, event) if policy is not None else None
        if grant is None:
            raise PermissionError("Event content is not authorized for this handler")
        # payload.records必须逐记录授权；不可通过动作字段一口气读出内部DTO或file引用。
        if "records" in grant.payload_fields:
            raise ValueError("Record bodies cannot be granted as an action field")
        if any(ref not in event.subject_refs for ref in grant.subject_refs):
            raise ValueError("Public subjects must come from the event")
        return grant

    async def _event(self, access: ReadAccess, identity: UUID) -> EventFact:
        async with self.engine.connect() as connection:
            value = await connection.scalar(
                text(
                    "SELECT to_jsonb(e) FROM runtime.events e WHERE event_id=:id "
                    "AND (scope_kind || ':' || scope_id::text)=ANY(:scopes)"
                ),
                {"id": identity, "scopes": [f"{kind}:{id}" for kind, id in access.scopes]},
            )
        if value is None:
            # 未授权空间与不存在的ID走相同拒绝，不暴露其他空间是否存在该事件。
            raise PermissionError("Event is not available in the authorized scope")
        return EventFact.model_validate_json(canonical_json(value))

    async def _upper(self, scope: tuple[str, UUID]) -> int:
        async with self.engine.connect() as connection:
            value = await connection.scalar(
                text(
                    "SELECT last_seq FROM runtime.scope_event_heads "
                    "WHERE scope_kind=:kind AND scope_id=:scope"
                ),
                {"kind": scope[0], "scope": scope[1]},
            )
        return int(value or 0)

    @staticmethod
    def _limit(limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= PAGE_MAX:
            raise ValueError("Page limit must be between 1 and 100")

    def _binding(self, access: ReadAccess, scope: tuple[str, UUID], filters: EventFilter) -> str:
        # 包含完整的本次授权边界，身份/用途/筛选变化后旧游标不能继续使用。
        value = {
            "principal": access.principal_id,
            "handler": access.handler_id,
            "module": access.module,
            "purpose": access.purpose,
            "authorization": access.authorization_ref,
            "scopes": sorted(f"{kind}:{id}" for kind, id in access.scopes),
            "sources": sorted(str(id) for id in access.source_event_ids)
            if access.source_event_ids is not None
            else None,
            "resources": [ref.model_dump(mode="json") for ref in access.resource_refs],
            "execution": str(access.execution_ref) if access.execution_ref else None,
            "maintenance": access.maintenance_ref,
            "scope": [scope[0], str(scope[1])],
            "filter": self._filter_json(filters),
        }
        return hashlib.sha256(canonical_json(value).encode()).hexdigest()

    @staticmethod
    def _filter_json(filters: EventFilter) -> dict[str, JsonValue]:
        for date in (filters.recorded_from, filters.recorded_to):
            if date is not None and date.utcoffset() is None:
                raise ValueError("Filter timestamps must include timezone")
        if (
            filters.recorded_from is not None
            and filters.recorded_to is not None
            and filters.recorded_from >= filters.recorded_to
        ):
            raise ValueError("Invalid recorded time interval")
        return {
            "types": [item for item in sorted(set(filters.event_types))],
            "subject": filters.subject_ref.model_dump(mode="json") if filters.subject_ref else None,
            "correlation": str(filters.correlation_id) if filters.correlation_id else None,
            "cause": str(filters.causation_event_id) if filters.causation_event_id else None,
            "from": filters.recorded_from.isoformat() if filters.recorded_from else None,
            "to": filters.recorded_to.isoformat() if filters.recorded_to else None,
        }

    def _encode(self, binding: str, after: int, upper: int) -> str:
        data = canonical_json({"v": 1, "binding": binding, "after": after, "upper": upper}).encode()
        signed = hmac.digest(self._key, data, "sha256") + data
        return base64.urlsafe_b64encode(signed).decode()

    def _decode(self, token: str, binding: str) -> tuple[int, int]:
        if len(token) > 2048:
            raise ValueError("Invalid cursor")
        try:
            signed = base64.b64decode(token, altchars=b"-_", validate=True)
            signature, data = signed[:32], signed[32:]
            if not hmac.compare_digest(signature, hmac.digest(self._key, data, "sha256")):
                raise ValueError("Invalid cursor signature")
            payload = json.loads(data)
            if (
                set(payload) != {"v", "binding", "after", "upper"}
                or payload["v"] != 1
                or payload["binding"] != binding
                or type(payload["after"]) is not int
                or type(payload["upper"]) is not int
                or not 0 <= payload["after"] <= payload["upper"]
            ):
                raise ValueError("Cursor does not match this query")
            return payload["after"], payload["upper"]
        except (TypeError, KeyError, json.JSONDecodeError) as error:
            raise ValueError("Invalid cursor") from error

    async def _ids(
        self,
        scope: tuple[str, UUID],
        after: int,
        upper: int,
        limit: int,
        filters: EventFilter | None,
    ) -> list[UUID]:
        """先取有限身份，再逐件取正文，避免把100份大payload同时装入内存。"""
        clauses = [
            "scope_kind=:kind",
            "scope_id=:scope",
            "scope_event_seq>:after",
            "scope_event_seq<=:upper",
        ]
        parameters: dict[str, object] = {
            "kind": scope[0],
            "scope": scope[1],
            "after": after,
            "upper": upper,
            "limit": limit,
        }
        if filters is not None:
            if filters.event_types:
                clauses.append("event_type=ANY(:types)")
                parameters["types"] = list(filters.event_types)
            for column, value, expression in (
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
        statement = "SELECT event_id FROM runtime.events WHERE " + " AND ".join(clauses)
        async with self.engine.connect() as connection:
            return list(
                await connection.scalars(
                    text(statement + " ORDER BY scope_event_seq LIMIT :limit"),
                    parameters,
                )
            )

    @staticmethod
    def _summary(event: EventFact, grant: ReadGrant) -> dict[str, JsonValue]:
        return {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "schema_version": event.schema_version,
            "scope_kind": event.scope_kind,
            "scope_id": str(event.scope_id),
            "scope_event_seq": event.scope_event_seq,
            "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
            "recorded_at": event.recorded_at.isoformat(),
            "time_basis": event.time_basis,
            "owner_ref": event.owner_ref.model_dump(mode="json", exclude_none=True),
            "subject_refs": [
                ref.model_dump(mode="json", exclude_none=True) for ref in grant.subject_refs
            ],
            "summary": grant.summary,
        }

    @staticmethod
    def _response(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if len(canonical_json(value).encode()) > RESPONSE_LIMIT:
            raise ValueError("Response exceeds 4MiB; request a smaller range")
        return value

    async def query_events(
        self,
        access: ReadAccess,
        scope_kind: str,
        scope_id: UUID,
        *,
        filters: EventFilter | None = None,
        cursor: str | None = None,
        limit: int = PAGE_DEFAULT,
    ) -> dict[str, JsonValue]:
        self._access(access)
        self._limit(limit)
        scope = (scope_kind, scope_id)
        if scope not in access.scopes:
            raise PermissionError("Query scope is not authorized")
        filters = filters or EventFilter()
        binding = self._binding(access, scope, filters)
        after, upper = self._decode(cursor, binding) if cursor else (0, await self._upper(scope))
        identities = await self._ids(scope, after, upper, limit + 1, filters)
        items: list[JsonValue] = []
        scanned = after
        for identity in identities[:limit]:
            event = await self._event(access, identity)
            scanned = event.scope_event_seq
            try:
                grant = self._grant(access, event)
            except PermissionError:
                continue
            items.append(self._summary(event, grant))
        return self._response(
            {
                "items": items,
                "upper_seq": upper,
                "next_cursor": self._encode(binding, scanned, upper)
                if len(identities) > limit
                else None,
            }
        )

    async def read_scope_events(
        self,
        access: ReadAccess,
        scope_kind: str,
        scope_id: UUID,
        *,
        after_seq: int,
        through_seq: int | None = None,
        types: tuple[str, ...] = (),
        limit: int = PAGE_DEFAULT,
    ) -> dict[str, JsonValue]:
        """消费者连续扫描；空匹配页仍返回已扫描进度，失败不返回可推进的游标。"""
        self._access(access)
        self._limit(limit)
        scope = (scope_kind, scope_id)
        if scope not in access.scopes or access.purpose in {"student_history", "admin_review"}:
            raise PermissionError("Continuous scanning requires an internal handler")
        current = await self._upper(scope)
        upper = current if through_seq is None else through_seq
        if (
            type(after_seq) is not int
            or type(upper) is not int
            or not 0 <= after_seq <= upper <= current
        ):
            raise ValueError("Invalid scan bounds")
        identities = await self._ids(scope, after_seq, upper, limit, None)
        scanned = after_seq
        items: list[JsonValue] = []
        for identity in identities:
            event = await self._event(access, identity)
            scanned = event.scope_event_seq
            if types and event.event_type not in types:
                continue
            items.append(self._summary(event, self._grant(access, event)))
        if len(identities) < limit:
            scanned = upper
        return self._response({"items": items, "upper_seq": upper, "scanned_through_seq": scanned})

    async def _body(
        self,
        event: EventFact,
        record_id: str,
        budget: int,
    ) -> tuple[dict[str, JsonValue], str, int, int]:
        registration = self._events[(event.event_type, event.schema_version)]
        payload = registration.payload_model.model_validate_json(canonical_json(event.payload))
        records = [record for record in payload.records if record.record_id == record_id]
        if len(records) != 1:
            raise ValueError("Fact record is missing or ambiguous")
        record = records[0]
        model = registration.record_models.get((record.record_type, record.schema_version))
        if model is None:
            raise ValueError("Fact record schema is not registered")
        if isinstance(record.content, InlineContent):
            content = record.content.value
            encoded = canonical_json(content).encode()
        else:
            reference = record.content
            async with self.engine.connect() as connection:
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
        return content, record.record_type, record.schema_version, len(encoded)

    async def read_event_facts(
        self,
        access: ReadAccess,
        refs: Sequence[EventPartRef],
        *,
        purpose: str,
    ) -> dict[str, JsonValue]:
        """批量顺序与输入一致；先授权再解包，每一跳重新授权，不递归抓取引用。"""
        self._access(access, purpose)
        self._limit(len(refs))
        items: list[JsonValue] = []
        budget = FACT_READ_LIMIT
        for ref in refs:
            parts = pointer_parts(ref.path)
            event = await self._event(access, ref.event_id)
            grant = self._grant(access, event)
            registration = self._events[(event.event_type, event.schema_version)]
            payload = registration.payload_model.model_validate_json(canonical_json(event.payload))
            if ref.record_id is None:
                fields: frozenset[str] | None = grant.payload_fields
                content = {key: value for key, value in event.payload.items() if key != "records"}
                schema: dict[str, JsonValue] = {
                    "event_type": event.event_type,
                    "schema_version": event.schema_version,
                }
                consumed = len(canonical_json(content).encode())
            else:
                record = next(
                    (item for item in payload.records if item.record_id == ref.record_id), None
                )
                if record is None:
                    raise ValueError("Fact record does not exist")
                key = (record.record_type, record.schema_version)
                if key not in grant.record_fields:
                    raise PermissionError("Fact record is not authorized")
                fields = grant.record_fields[key]
                # 私有字段不能借整个附件下载；拒绝发生在任何文件读取之前。
                if parts and fields is not None and parts[0] not in fields:
                    raise PermissionError("Fact field is not authorized")
                content, kind, version, consumed = await self._body(event, ref.record_id, budget)
                schema = {"record_type": kind, "schema_version": version}
            if parts and fields is not None and parts[0] not in fields:
                raise PermissionError("Fact field is not authorized")
            budget -= consumed
            if budget < 0:
                raise ValueError("Fact reading exceeds the 32MiB budget")
            missing: list[str] = []
            result: JsonValue
            if parts:
                try:
                    result = fragment(content, parts)
                except (KeyError, IndexError):
                    result = None
                    missing = ["field_missing"]
                visible = [ref.path]
                visibility = "complete"
            else:
                result = (
                    content
                    if fields is None
                    else {key: content[key] for key in fields if key in content}
                )
                visible = (
                    [""]
                    if fields is None
                    else ["/" + key.replace("~", "~0").replace("/", "~1") for key in sorted(fields)]
                )
                missing = (
                    []
                    if fields is None
                    else [f"field_missing:{key}" for key in sorted(fields - content.keys())]
                )
                visibility = "complete" if fields is None or fields == content.keys() else "partial"
            items.append(
                {
                    "ref": ref.model_dump(mode="json"),
                    "schema_ref": schema,
                    "content": result,
                    "sha256": hashlib.sha256(canonical_json(result).encode()).hexdigest(),
                    "visible_paths": [item for item in visible],
                    "visibility": visibility,
                    "completeness": "incomplete" if missing else "complete",
                    "missing_reasons": [item for item in missing],
                }
            )
            self._response({"items": items})
        return {"items": items}

    async def read_projection_event(self, access: ReadAccess, identity: UUID) -> StoredEvent:
        """维护重建取得完整已校验事件；沿用授权和读取限额，不接受裁剪后的正文。"""
        self._access(access, "projection_rebuild")
        event = await self._event(access, identity)
        self._grant(access, event)
        registration = self._events[(event.event_type, event.schema_version)]
        if registration.producer != event.producer or registration.scope_kind != event.scope_kind:
            raise ValueError("Stored event does not match its registration")
        wire = registration.payload_model.model_validate_json(canonical_json(event.payload))
        refs = [EventPartRef(event_id=identity, record_id=None, path="")]
        refs.extend(
            EventPartRef(event_id=identity, record_id=record.record_id, path="")
            for record in wire.records
        )
        response = await self.read_event_facts(access, refs, purpose="projection_rebuild")
        items = TypeAdapter(list[dict[str, JsonValue]]).validate_python(response["items"])
        if any(
            item["visibility"] != "complete" or item["completeness"] != "complete" for item in items
        ):
            raise PermissionError("Projection requires complete action and record bodies")
        body = JSON_OBJECT.validate_python(items[0]["content"], strict=True)
        body["records"] = [
            record.model_copy(
                update={
                    "content": InlineContent(
                        storage="inline",
                        value=JSON_OBJECT.validate_python(item["content"], strict=True),
                    )
                }
            ).model_dump(mode="json")
            for record, item in zip(wire.records, items[1:], strict=True)
        ]
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
        )
