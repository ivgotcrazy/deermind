"""追加事实并应用已登记的生产者投影；提交和回滚由外层用例负责。"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from uuid import UUID

from deermind.foundation.system.events.contracts import (
    EVENT_LIMIT,
    INLINE_LIMIT,
    EventConflict,
    EventDraft,
    EventPayload,
    EventRegistration,
    FileContent,
    InlineContent,
    PreparedEvents,
    ProducerAccess,
    StoredEvent,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


def canonical_json(value: object) -> str:
    """固定UTF-8 JSON编码：键排序、无空白、拒绝非有限数；不改变数组顺序。"""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


class EventStore:
    """由装配层登记白名单；每次保存使用调用方已开启的同一事务。"""

    def __init__(self, registrations: Sequence[EventRegistration]) -> None:
        self._registry: dict[tuple[str, int], EventRegistration] = {}
        for registration in registrations:
            key = (registration.event_type, registration.schema_version)
            if key in self._registry:
                raise ValueError("Duplicate event registration")
            self._registry[key] = registration

    async def append_and_project(
        self,
        connection: AsyncConnection,
        access: ProducerAccess,
        drafts: Sequence[EventDraft] | PreparedEvents,
        *,
        commit_id: UUID,
        correlation_id: UUID,
        expected_seq: Mapping[tuple[str, UUID], int],
    ) -> list[StoredEvent]:
        """先校验整批，再按固定顺序锁序号头；任何异常必须由外层回滚。

        调用前取得业务锁。投影只处理已保护或本次新建的对象，不取新业务锁。
        此入口不发送通知、不调用AI、不推进订阅扫描游标。
        """
        if not connection.in_transaction() or not drafts:
            raise ValueError("An active transaction and a nonempty event batch are required")
        if isinstance(drafts, PreparedEvents):
            prepared = drafts
            drafts = prepared.drafts
        else:
            prepared = None
            drafts = tuple(drafts)
        if not drafts:
            raise ValueError("An event batch cannot be empty")
        expected_seq = dict(expected_seq)
        if prepared is not None:
            if prepared.access != access or len(prepared.decoded_payloads) != len(drafts):
                raise PermissionError("Prepared facts belong to a different producer context")
            decoded_drafts = tuple(
                replace(draft, payload=json.loads(payload))
                for draft, payload in zip(drafts, prepared.decoded_payloads, strict=True)
            )
            validated = self.validate_inline(access, decoded_drafts)
        else:
            validated = self.validate_inline(access, drafts)
        await self._check_content(connection, drafts, validated)
        scopes = {(draft.scope_kind, draft.scope_id) for draft in drafts}
        if set(expected_seq) != scopes or any(
            type(n) is not int or n < 0 for n in expected_seq.values()
        ):
            raise ValueError("Expected sequence must cover exactly this batch's scopes")

        # 先锁所有范围，防止多范围提交按不同顺序互相等待。
        sequences: dict[tuple[str, UUID], int] = {}
        for kind, scope_id in sorted(scopes, key=lambda scope: (scope[0], str(scope[1]))):
            parameters = {"kind": kind, "id": scope_id}
            await connection.execute(
                text(
                    "INSERT INTO runtime.scope_event_heads(scope_kind, scope_id, last_seq) "
                    "VALUES (:kind, :id, 0) ON CONFLICT DO NOTHING"
                ),
                parameters,
            )
            current = await connection.scalar(
                text(
                    "SELECT last_seq FROM runtime.scope_event_heads "
                    "WHERE scope_kind=:kind AND scope_id=:id FOR UPDATE"
                ),
                parameters,
            )
            if current != expected_seq[kind, scope_id]:
                raise EventConflict("Event scope has changed")
            sequences[kind, scope_id] = current

        stored: list[StoredEvent] = []
        for draft, (registration, payload) in zip(drafts, validated, strict=True):
            scope = (draft.scope_kind, draft.scope_id)
            sequences[scope] += 1
            # clock_timestamp取当前记录时点，不取事务启动时间。
            recorded_at = await connection.scalar(text("SELECT clock_timestamp()"))
            if not isinstance(recorded_at, datetime):
                raise RuntimeError("Database did not return a timestamp")
            event = StoredEvent(
                draft, commit_id, correlation_id, sequences[scope], recorded_at, payload
            )
            await self._insert(connection, access, event)
            await registration.project(connection, event)
            await connection.execute(
                text(
                    "INSERT INTO runtime.projection_receipts "
                    "(projector_id, generation, event_id, applied_at) "
                    "VALUES (:projector, 1, :event, clock_timestamp())"
                ),
                {"projector": registration.projector_id, "event": draft.event_id},
            )
            stored.append(event)

        for (kind, scope_id), sequence in sequences.items():
            await connection.execute(
                text(
                    "UPDATE runtime.scope_event_heads SET last_seq=:seq "
                    "WHERE scope_kind=:kind AND scope_id=:id"
                ),
                {"kind": kind, "id": scope_id, "seq": sequence},
            )
        return stored

    def validate_inline(
        self, access: ProducerAccess, drafts: Sequence[EventDraft]
    ) -> list[tuple[EventRegistration, EventPayload]]:
        """所有者验证记录矩阵与正文；未登记类型、错范围和重复身份一律拒绝。"""
        event_ids = [draft.event_id for draft in drafts]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("Duplicate event identity in batch")
        remaining = set(event_ids)
        result: list[tuple[EventRegistration, EventPayload]] = []
        for draft in drafts:
            registration = self._registry.get((draft.event_type, draft.schema_version))
            if registration is None:
                raise ValueError("Event type or schema version is not registered")
            if (
                registration.producer != access.producer
                or registration.scope_kind != draft.scope_kind
                or (draft.scope_kind, draft.scope_id) not in access.scopes
            ):
                raise PermissionError("Producer is not authorized for this event scope")
            if not draft.source_request_id and draft.causation_event_id is None:
                raise ValueError("An event requires a request or a preceding fact")
            if draft.causation_event_id in remaining:
                raise ValueError("A cause must precede this event")
            if (
                draft.causation_event_id is not None
                and draft.causation_event_id not in event_ids
                and draft.causation_event_id not in access.source_event_ids
            ):
                raise PermissionError("The preceding fact is not in the authorized source set")
            remaining.remove(draft.event_id)
            # 从固定JSON解码，UUID/UTC等正文由其登记Schema严格校验。
            payload = registration.payload_model.model_validate_json(canonical_json(draft.payload))
            if any(not isinstance(record.content, InlineContent) for record in payload.records):
                raise ValueError("File-backed facts require verified attachment preparation")
            record_ids = [record.record_id for record in payload.records]
            if len(record_ids) != len(set(record_ids)):
                raise ValueError("Duplicate record identity in event")
            registration.validate(draft, payload)
            result.append((registration, payload))
        return result

    @staticmethod
    async def _check_content(
        connection: AsyncConnection,
        drafts: Sequence[EventDraft],
        validated: list[tuple[EventRegistration, EventPayload]],
    ) -> None:
        """只查不可变文件登记，不在业务事务内读文件；核对外置与完整DTO一致。"""
        for draft, (registration, decoded) in zip(drafts, validated, strict=True):
            wire = registration.payload_model.model_validate_json(canonical_json(draft.payload))
            if len(wire.records) != len(decoded.records):
                raise ValueError("Prepared record count changed")
            for record, full in zip(wire.records, decoded.records, strict=True):
                if not isinstance(full.content, InlineContent):
                    raise ValueError("Decoded record must contain its complete DTO")
                content = canonical_json(full.content.value).encode("utf-8")
                if isinstance(record.content, FileContent):
                    reference = record.content
                    if reference.sha256 != hashlib.sha256(content).hexdigest():
                        raise ValueError("Attachment hash differs from its decoded DTO")
                    row = (
                        await connection.execute(
                            text(
                                "SELECT sha256, byte_size, media_type, artifact_key "
                                "FROM runtime.file_objects WHERE file_id=:id"
                            ),
                            {"id": reference.file_id},
                        )
                    ).one_or_none()
                    if row != (
                        reference.sha256,
                        len(content),
                        reference.media_type,
                        f"fact:{draft.event_id}:{record.record_id}",
                    ):
                        raise ValueError("Attachment is not registered for this fact record")
                else:
                    if record.content != full.content:
                        raise ValueError("Prepared inline content changed")
                    if len(content) > INLINE_LIMIT:
                        raise ValueError("Large fact record must be prepared as an attachment")
            restored = wire.model_copy(
                update={
                    "records": [
                        record.model_copy(update={"content": full.content})
                        for record, full in zip(wire.records, decoded.records, strict=True)
                    ]
                }
            )
            if restored != decoded:
                raise ValueError("Prepared event metadata changed")

    @staticmethod
    async def _insert(
        connection: AsyncConnection, access: ProducerAccess, event: StoredEvent
    ) -> None:
        draft = event.draft
        # 大小包括完整信封，而不是只计算payload。UTC时间使用实际保存值。
        envelope = {
            "event_id": str(draft.event_id),
            "commit_id": str(event.commit_id),
            "event_type": draft.event_type,
            "schema_version": draft.schema_version,
            "producer": access.producer,
            "scope_kind": draft.scope_kind,
            "scope_id": str(draft.scope_id),
            "owner_ref": draft.owner_ref.model_dump(),
            "subject_refs": [ref.model_dump() for ref in draft.subject_refs],
            "actor_ref": access.actor_ref.model_dump(),
            "source_execution_ref": str(draft.source_execution_ref)
            if draft.source_execution_ref
            else None,
            "source_request_id": draft.source_request_id,
            "causation_event_id": str(draft.causation_event_id)
            if draft.causation_event_id
            else None,
            "correlation_id": str(event.correlation_id),
            "scope_event_seq": event.scope_event_seq,
            "occurred_at": event.recorded_at.isoformat(),
            "recorded_at": event.recorded_at.isoformat(),
            "time_basis": "server_recorded",
            "time_source_ref": None,
            "client_reported_at": None,
            "payload": draft.payload,
        }
        if len(canonical_json(envelope).encode("utf-8")) > EVENT_LIMIT:
            raise ValueError("Encoded event exceeds 1MiB")
        await connection.execute(
            text(
                "INSERT INTO runtime.events "
                "(event_id, commit_id, event_type, schema_version, producer, scope_kind, scope_id, "
                "owner_ref, subject_refs, actor_ref, source_execution_ref, source_request_id, "
                "causation_event_id, correlation_id, scope_event_seq, occurred_at, recorded_at, "
                "time_basis, time_source_ref, client_reported_at, payload) VALUES "
                "(:event_id, :commit_id, :type, :version, :producer, :kind, :scope, "
                "CAST(:owner AS jsonb), CAST(:subjects AS jsonb), CAST(:actor AS jsonb), "
                ":execution, :request, :cause, :correlation, :seq, :time, :time, "
                "'server_recorded', NULL, NULL, CAST(:payload AS jsonb))"
            ),
            {
                "event_id": draft.event_id,
                "commit_id": event.commit_id,
                "type": draft.event_type,
                "version": draft.schema_version,
                "producer": access.producer,
                "kind": draft.scope_kind,
                "scope": draft.scope_id,
                "owner": draft.owner_ref.model_dump_json(exclude_none=True),
                "subjects": canonical_json(
                    [ref.model_dump(exclude_none=True) for ref in draft.subject_refs]
                ),
                "actor": access.actor_ref.model_dump_json(exclude_none=True),
                "execution": draft.source_execution_ref,
                "request": draft.source_request_id,
                "cause": draft.causation_event_id,
                "correlation": event.correlation_id,
                "seq": event.scope_event_seq,
                "time": event.recorded_at,
                "payload": canonical_json(draft.payload),
            },
        )
