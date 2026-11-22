"""固定题目、现有定义和依据，保存模型建议供普通入库流程核对。"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid5

from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from deermind.abstractions.ai.contracts import ExecutionConfig
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, FactRecord, InlineContent, ProducerAccess, Ref
from deermind.abstractions.executions import Authorization, Execution, RunInput, State
from deermind.abstractions.hashing import digest
from deermind.abstractions.material_intake import IntakeSource
from deermind.foundation.ai import store as ai_store
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.executions import commands, store
from deermind.foundation.system.executions.contracts import Caller, Entry, Registry
from deermind.foundation.system.public.errors import ErrorDetail, RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.spaces.domain import analysis_facts as facts
from deermind.spaces.domain.instances import load_instance
from deermind.spaces.domain.intake import DomainIntake, IntakeItem
from deermind.spaces.domain.public import (
    CLASSIFY,
    EXTRACT,
    AnalysisAcceptance,
    AnalysisArtifactView,
    AnalysisOutput,
    AnalysisReceipt,
    CheckClassification,
    CheckManualInstance,
    DraftDefinition,
    ExtractDefinition,
    SolutionDefinition,
    SolutionRef,
    TaskDefinition,
    TaskInstance,
    TaskRef,
)

WORKFLOW = "domain.ContentAnalysis"
type GuardSource = Callable[[AsyncConnection, UUID, IntakeSource], Awaitable[None]]
type Command = ExtractDefinition | CheckClassification | CheckManualInstance


def artifact_ref(identity: UUID) -> Ref:
    return Ref(owner="domain", type="artifact", id=str(identity))


def _structured(value: str | None) -> dict[str, JsonValue] | None:
    if value is None:
        return None
    return {
        "schema_version": "1",
        "role": "definition",
        "data_tables": [],
        "source_refs": [],
        "blocks": [
            {
                "block_id": "text",
                "type": "paragraph",
                "provenance": {"source_refs": [], "transformation": "generated"},
                "payload": {"spans": [{"type": "text", "text": value}]},
            }
        ],
    }


def location_tables(data: dict[str, JsonValue]) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """为模型提供可选短编号，位置由已固定的材料生成。"""
    materials: dict[str, str] = {}
    for key in ("candidate", "parent"):
        source = data[key]
        if not isinstance(source, dict):
            continue
        body = source.get("body")
        content = body.get("content") if isinstance(body, dict) else None
        blocks = content.get("blocks") if isinstance(content, dict) else None
        if isinstance(blocks, list):
            for index, _block in enumerate(blocks):
                materials[f"M{len(materials) + 1}"] = f"/{key}/body/content/blocks/{index}"
        references = body.get("references") if isinstance(body, dict) else None
        if isinstance(references, list):
            for index, reference in enumerate(references):
                if isinstance(reference, dict):
                    materials[f"M{len(materials) + 1}"] = f"/{key}/body/references/{index}"
    definitions: dict[str, dict[str, str]] = {}
    next_location = 1
    candidates = data["definitions"]
    assert isinstance(candidates, dict)
    for key in sorted(candidates, key=lambda key: key != "task"):
        value = candidates[key]
        assert isinstance(value, dict)
        available = [field for field, content in sorted(value.items()) if content not in (None, [])]
        definitions[key] = {
            f"D{index}": f"/{field}" for index, field in enumerate(available, next_location)
        }
        next_location += len(available)
    return materials, definitions


def _definition(proposed: DraftDefinition) -> dict[str, JsonValue]:
    fields = (
        (
            "responsibility",
            "expected_output",
            "completion_conditions",
            "applicability",
            "boundaries",
        )
        if proposed.kind == "task"
        else ("approach", "rationale", "applicability", "key_process")
    )
    values = {
        "name": proposed.name,
        **{field: _structured(getattr(proposed, field)) for field in fields},
    }
    schema = TaskDefinition if proposed.kind == "task" else SolutionDefinition
    return schema.model_validate(values).model_dump(mode="json")


def accepted_output(
    data: dict[str, JsonValue], output: AnalysisOutput
) -> dict[str, JsonValue] | None:
    """检查模型引用只落在本次材料和固定候选上。"""
    materials, candidates = location_tables(data)
    keyed = {entry.candidate_key: entry for entry in output.results}
    if len(keyed) != len(output.results) or set(keyed) != set(candidates):
        raise ValueError("Model results must cover the provided candidates exactly once")
    for key, entry in keyed.items():
        if entry.result == "matched" and not any(
            item.material_locations and item.definition_locations for item in entry.findings
        ):
            raise ValueError("A match needs material and definition evidence")
        if entry.result != "matched" and not (entry.findings or entry.issues):
            raise ValueError("A nonmatch needs a concrete reason")
        for finding in entry.findings:
            if not set(finding.material_locations) <= materials.keys():
                raise ValueError("Evidence is outside the supplied material")
            if not set(finding.definition_locations) <= candidates[key].keys():
                raise ValueError("Evidence is outside the supplied definition")
    if output.draft is None:
        if data["action"] == EXTRACT and not output.unresolved:
            raise ValueError("Missing extraction proposal or explicit gap")
        return None
    if data["action"] != EXTRACT or output.draft.kind != data["subject_kind"]:
        raise ValueError("Model returned a different proposal type")
    if not output.draft.evidence:
        raise ValueError("A definition proposal needs source evidence")
    if not set(output.draft.evidence) <= materials.keys():
        raise ValueError("Definition evidence is outside the supplied material")
    return _definition(output.draft)


class DomainAnalysis:
    def __init__(
        self,
        intake: DomainIntake,
        attachments: FactAttachments,
        guard_source: GuardSource,
        config: ExecutionConfig | None,
        queue: str,
    ) -> None:
        self.intake = intake
        self.engine = intake.engine
        self.event_store = intake.store
        self.attachments = attachments
        self.guard_source = guard_source
        self.config = config
        self.registry = Registry(
            [
                Entry(
                    "domain",
                    entry,
                    "ai_operation",
                    Ref(owner="domain", type="operation", id=entry, version=1),
                    WORKFLOW,
                    queue,
                    self.lock,
                    self.check,
                    self.finalize,
                )
                for entry in (EXTRACT, CLASSIFY)
            ]
        )

    async def lock(self, connection: AsyncConnection, scope: str, domain_id: UUID) -> None:
        if scope != "domain":
            raise PermissionError("Wrong analysis scope")
        result = await connection.scalar(
            text(
                "SELECT object_id FROM domain.object_identity "
                "WHERE object_id=:id AND kind='domain' FOR UPDATE"
            ),
            {"id": domain_id},
        )
        if result is None:
            raise RequestError(404, "not_found", "找不到领域。")

    async def check(
        self,
        connection: AsyncConnection,
        execution: Execution,
        _authorization: Authorization,
        action: str,
    ) -> None:
        fixed = await self._artifact(connection, execution.scope_id, UUID(execution.input_ref.id))
        if fixed.kind != "input" or fixed.payload.get("action") != execution.entry_ref:
            raise PermissionError("The fixed input belongs to another analysis")
        if action == "accept" and fixed.command_ref is None:
            raise PermissionError("Analysis requires an accepted request")

    async def finalize(
        self, connection: AsyncConnection, work: Execution, state: State, result: Ref | None
    ) -> None:
        if state not in ("completed", "failed", "cancelled"):
            return
        fixed = await self._artifact(connection, work.scope_id, UUID(work.input_ref.id))
        assert fixed.command_ref is not None
        error = (
            None
            if state == "completed"
            else canonical_json(
                {
                    "code": "analysis_unavailable",
                    "message": "本次分析未完成，可保留原待办后重试。",
                    "retryable": True,
                    "issues": [],
                }
            )
        )
        await connection.execute(
            text(
                "UPDATE domain.command_receipt SET state=:state,result_ref=CAST(:result AS jsonb),"
                "error=CAST(:error AS jsonb),updated_at=clock_timestamp() WHERE receipt_id=:id"
            ),
            {
                "state": "completed" if state == "completed" else "failed",
                "result": result.model_dump_json() if result else None,
                "error": error,
                "id": UUID(fixed.command_ref.id),
            },
        )

    async def _artifact(
        self, connection: AsyncConnection, domain_id: UUID, identity: UUID
    ) -> facts.AnalysisArtifact:
        row = await connection.scalar(
            text(
                "SELECT to_jsonb(a)-'source_event_id' FROM domain.artifact a "
                "WHERE artifact_id=:id AND domain_id=:domain"
            ),
            {"id": identity, "domain": domain_id},
        )
        if row is None:
            raise RequestError(404, "not_found", "找不到此领域的产物。")
        return facts.AnalysisArtifact.model_validate_json(canonical_json(row))

    async def artifact(self, domain_id: UUID, identity: UUID) -> AnalysisArtifactView:
        async with self.engine.connect() as connection:
            value = await self._artifact(connection, domain_id, identity)
        if value.kind == "input":
            raise RequestError(404, "not_found", "找不到可查看的检查产物。")
        return AnalysisArtifactView(artifact=value.model_dump(mode="json"))

    async def require_match(
        self,
        connection: AsyncConnection,
        domain_id: UUID,
        item: IntakeItem,
        check: Ref | None,
        definitions: list[Ref],
        *,
        adding_method: bool = False,
        parent_statement: dict[str, JsonValue] | None = None,
    ) -> None:
        if check is None or check.owner != "domain" or check.type != "artifact":
            raise RequestError(409, "classification_required", "请先核对分类结果。")
        checked = await self._artifact(connection, domain_id, UUID(check.id))
        if checked.kind != "classification_check" or checked.definition_refs != definitions:
            raise RequestError(409, "classification_stale", "归类使用的定义已有变化，请重新检查。")
        fixed = await self._artifact(connection, domain_id, UUID(checked.input_ref.id))
        if (
            fixed.input_ref != item.reference()
            or bool(fixed.payload.get("adding_method")) != adding_method
        ):
            raise RequestError(409, "classification_stale", "归类使用的待办已有变化，请重新检查。")
        if parent_statement is not None:
            parent = fixed.payload.get("parent")
            body = parent.get("body") if isinstance(parent, dict) else None
            if not isinstance(body, dict) or body.get("content") != parent_statement:
                raise RequestError(
                    409, "classification_stale", "归类使用的父题题面已变化，请重新检查。"
                )
        result = AnalysisReceipt.model_validate_json(canonical_json(checked.payload))
        outcomes = {entry.result for entry in result.output.results}
        if not outcomes or outcomes != {"matched"}:
            code = (
                "classification_failed" if "mismatch" in outcomes else "classification_unresolved"
            )
            raise RequestError(409, code, "本次归类没有确认符合，请核对依据并重新选择。")

    async def require_instance_match(
        self,
        connection: AsyncConnection,
        domain_id: UUID,
        instance: TaskInstance,
        check: Ref | None,
    ) -> None:
        if check is None or check.owner != "domain" or check.type != "artifact":
            raise RequestError(409, "classification_required", "请先检查此题目版本。")
        checked = await self._artifact(connection, domain_id, UUID(check.id))
        if checked.kind != "classification_check":
            raise RequestError(409, "classification_required", "请选择题目归类检查结果。")
        fixed = await self._artifact(connection, domain_id, UUID(checked.input_ref.id))
        if fixed.payload.get("manual_instance") != instance.model_dump(mode="json"):
            raise RequestError(409, "classification_stale", "题面或参考已变化，请重新检查。")
        result = AnalysisReceipt.model_validate_json(canonical_json(checked.payload))
        if {entry.result for entry in result.output.results} != {"matched"}:
            raise RequestError(409, "classification_failed", "分类检查尚未确认符合。")

    async def _definitions(
        self,
        connection: AsyncConnection,
        domain_id: UUID,
        kind: str,
        command: Command,
    ) -> tuple[dict[str, JsonValue], list[Ref]]:
        selected: list[TaskRef | SolutionRef]
        if isinstance(command, CheckClassification):
            selected = [command.task_ref, *([command.solution_ref] if command.solution_ref else [])]
        elif isinstance(command, CheckManualInstance):
            selected = [command.instance.task_ref]
            for entry in command.instance.reference_solutions:
                if entry.solution_ref not in selected:
                    selected.append(entry.solution_ref)
        else:
            selected = []
        rows: list[Row[tuple[UUID, str, int, dict[str, JsonValue]]]] = []
        if selected:
            for ref in selected:
                row = (
                    await connection.execute(
                        text(
                            "SELECT i.object_id,i.kind,v.version,v.content "
                            "FROM domain.object_identity i "
                            "JOIN domain.object_version v USING(object_id) "
                            "JOIN domain.object_version h "
                            "ON (h.object_id,h.version)=(i.object_id,i.head_version) "
                            "WHERE i.domain_id=:domain AND i.kind=:kind AND v.object_id=:id "
                            "AND v.version=:version AND NOT h.is_deleted AND NOT v.is_deleted"
                        ),
                        {
                            "domain": domain_id,
                            "id": ref.object_id,
                            "kind": ref.kind,
                            "version": ref.version,
                        },
                    )
                ).one_or_none()
                if row is None:
                    raise RequestError(409, "invalid_reference", "所选定义已经不可用。")
                rows.append(row)
        else:
            # 只提供少量确定的候选；空结果不代表整个领域找不到定义。
            rows = list(
                (
                    await connection.execute(
                        text(
                            "SELECT i.object_id,i.kind,v.version,v.content "
                            "FROM domain.object_identity i JOIN domain.object_version v "
                            "ON (v.object_id,v.version)=(i.object_id,i.head_version) "
                            "WHERE i.domain_id=:domain AND i.kind=:kind AND NOT v.is_deleted "
                            "ORDER BY v.created_at DESC,i.object_id LIMIT 5"
                        ),
                        {"domain": domain_id, "kind": kind},
                    )
                ).all()
            )
        contents: dict[str, JsonValue] = {}
        refs: list[Ref] = []
        for row in rows:
            key = row.kind if selected else f"definition-{len(refs) + 1}"
            if isinstance(command, CheckManualInstance) and row.kind == "solution":
                key = f"method-{len(refs)}"
            ref = Ref(owner="domain", type=row.kind, id=str(row.object_id), version=row.version)
            contents[key] = row.content
            refs.append(ref)
        return contents, refs

    async def _snapshot(
        self,
        domain_id: UUID,
        command: Command,
    ) -> tuple[IntakeItem | None, dict[str, JsonValue], list[Ref]]:
        if isinstance(command, CheckManualInstance):
            instance = command.instance
            async with self.engine.connect() as connection:
                definitions, refs = await self._definitions(connection, domain_id, "task", command)
            return (
                None,
                {
                    "action": CLASSIFY,
                    "subject_kind": "task",
                    "manual_instance": instance.model_dump(mode="json"),
                    "candidate": {
                        "body": {
                            "content": instance.statement.model_dump(mode="json"),
                            "references": [
                                entry.model_dump(mode="json")
                                for entry in instance.reference_solutions
                            ],
                        }
                    },
                    "parent": None,
                    "definitions": definitions,
                },
                refs,
            )
        ref = command.intake_item_ref
        if ref.owner != "domain" or ref.type != "intake_item" or ref.revision is None:
            raise RequestError(400, "invalid_reference", "请选择固定修订的待入库内容。")
        async with self.engine.connect() as connection:
            item = await self.intake.item(connection, domain_id, UUID(ref.id))
            if item.reference() != ref or item.state != "pending":
                raise RequestError(409, "source_changed", "待入库内容已变化，请刷新。")
            if item.kind not in ("task_instance", "reference"):
                raise RequestError(400, "invalid_reference", "此操作只适用于题目和题内参考。")
            kind = "task" if item.kind == "task_instance" else "solution"
            if isinstance(command, ExtractDefinition) and command.template_kind != kind:
                raise RequestError(400, "invalid_reference", "定义类型与待入库内容不一致。")
            if isinstance(command, CheckClassification) and (command.solution_ref is not None) != (
                kind == "solution"
            ):
                raise RequestError(400, "invalid_reference", "检查题内参考时必须选择对应方法。")
            definitions, refs = await self._definitions(connection, domain_id, kind, command)
            if isinstance(command, CheckClassification) and command.confirm_add_method:
                definition = definitions["task"]
                if not isinstance(definition, dict) or command.solution_ref is None:
                    raise RequestError(400, "invalid_reference", "请明确要加入任务的方法。")
                task = TaskDefinition.model_validate(definition)
                if command.solution_ref in task.method_refs:
                    raise RequestError(400, "invalid_reference", "此任务版本已经采用该方法。")
                proposed = task.model_copy(
                    update={
                        "method_refs": [*task.method_refs, command.solution_ref],
                    }
                )
                definitions["task"] = proposed.model_dump(mode="json")
            previous = None
            if isinstance(command, ExtractDefinition) and command.prior_candidate_ref:
                candidate = await self._artifact(
                    connection, domain_id, UUID(command.prior_candidate_ref.id)
                )
                if candidate.kind != "definition_candidate":
                    raise RequestError(400, "invalid_reference", "请选择已有的定义候选。")
                previous = candidate.payload
            parent: dict[str, JsonValue] | None = None
            reference = item.parent_instance_ref
            if item.parent_item_id is not None:
                parent_item = await self.intake.item(connection, domain_id, item.parent_item_id)
                reference = parent_item.result_ref if parent_item.state == "completed" else None
                if reference is None:
                    parent = await self.intake.candidate(parent_item)
            if reference is not None:
                instance = await load_instance(connection, domain_id, UUID(reference.id))
                if instance.is_deleted:
                    raise RequestError(409, "parent_not_linked", "父题已移除。")
                content: dict[str, JsonValue] = instance.content.statement.model_dump(mode="json")
                parent = {"body": {"content": content}}
        candidate = await self.intake.candidate(item)
        return (
            item,
            {
                "action": EXTRACT if isinstance(command, ExtractDefinition) else CLASSIFY,
                "subject_kind": kind,
                "candidate": candidate,
                "parent": parent,
                "definitions": definitions,
                "adding_method": isinstance(command, CheckClassification)
                and command.confirm_add_method,
                "prior_candidate": previous,
                "instruction": command.extraction_instruction
                if isinstance(command, ExtractDefinition)
                else None,
            },
            refs,
        )

    def _prepare(
        self,
        value: facts.AnalysisArtifact,
        kind: str,
        item: Ref,
        actor: Ref,
        request: UUID,
    ) -> tuple[ProducerAccess, EventDraft]:
        reference = artifact_ref(value.artifact_id)
        payload = facts.AnalysisFact(
            records=[
                FactRecord(
                    record_id=reference.id,
                    record_type=facts.ARTIFACT,
                    schema_version=1,
                    content=InlineContent(storage="inline", value=value.model_dump(mode="json")),
                )
            ],
            domain_id=value.domain_id,
            request_ref=request,
            artifact_ref=reference,
            intake_item_ref=item,
        )
        access = ProducerAccess("domain", actor, frozenset({("domain", value.domain_id)}))
        draft = EventDraft(
            uuid4(),
            kind,
            1,
            "domain",
            value.domain_id,
            reference,
            payload.model_dump(mode="json"),
            str(request),
            subject_refs=(item,),
        )
        return access, draft

    async def accept(
        self,
        domain_id: UUID,
        principal: UUID,
        command: Command,
    ) -> AnalysisAcceptance:
        config = self.config
        if config is None:
            raise RequestError(503, "temporarily_unavailable", "领域分析模型尚未配置。")
        action = EXTRACT if isinstance(command, ExtractDefinition) else CLASSIFY
        body = command.model_dump(mode="json")
        identity = uuid5(domain_id, f"{action}:{principal}:{command.request_id}")
        run_id = uuid5(identity, "execution")
        input_id = uuid5(identity, "analysis-input")
        actor = Ref(owner="product", type="account", id=str(principal))
        async with self.engine.connect() as connection:
            saved = await connection.scalar(
                text("SELECT input_hash FROM domain.command_receipt WHERE receipt_id=:id"),
                {"id": identity},
            )
        if saved is not None:
            if saved != digest(body):
                raise RequestError(409, "request_conflict", "请求编号已用于另一项分析。")
            return AnalysisAcceptance(request_ref=identity, operation_run_id=run_id)
        item, source, refs = await self._snapshot(domain_id, command)
        subject = (
            item.reference()
            if item is not None
            else Ref(owner="domain", type="proposed_instance", id=str(input_id))
        )
        fixed = facts.AnalysisArtifact(
            artifact_id=input_id,
            domain_id=domain_id,
            kind="input",
            input_ref=subject,
            definition_refs=refs,
            payload=source,
            rule_ref=None,
            model_call_ref=None,
            command_ref=Ref(owner="domain", type="request", id=str(identity)),
            created_at=datetime.now(UTC),
        )
        access, draft = self._prepare(fixed, facts.INPUT, subject, actor, identity)
        prepared = await self.attachments.prepare(self.event_store, access, (draft,))
        async with self.engine.begin() as connection:
            claimed = await connection.scalar(
                text(
                    "INSERT INTO domain.command_receipt "
                    "(receipt_id,principal_id,action,scope_id,request_id,normalized_input,input_hash,"
                    "state,runtime_ref,created_at,updated_at) VALUES "
                    "(:id,:principal,:action,:scope,:request,CAST(:body AS jsonb),:hash,"
                    "'accepted',:runtime,clock_timestamp(),clock_timestamp()) "
                    "ON CONFLICT (principal_id,action,scope_id,request_id) "
                    "DO NOTHING RETURNING receipt_id"
                ),
                {
                    "id": identity,
                    "principal": str(principal),
                    "action": action,
                    "scope": str(domain_id),
                    "request": command.request_id,
                    "body": canonical_json(body),
                    "hash": digest(body),
                    "runtime": run_id,
                },
            )
            if claimed is None:
                saved = await connection.scalar(
                    text("SELECT input_hash FROM domain.command_receipt WHERE receipt_id=:id"),
                    {"id": identity},
                )
                if saved != digest(body):
                    raise RequestError(409, "request_conflict", "请求编号已用于另一项分析。")
            else:
                if item is not None:
                    await self.guard_source(
                        connection, UUID(item.candidate_key.partition(":")[0]), item.source_ref
                    )
                await self.lock(connection, "domain", domain_id)
                if item is not None:
                    current = await self.intake.item(connection, domain_id, item.item_id)
                    if current.state != "pending" or current.reference() != item.reference():
                        raise RequestError(409, "source_changed", "待入库内容已变化，请刷新。")
                scope = ("domain", domain_id)
                sequence = await lock_scope_sequence(connection, *scope)
                (event,) = await self.event_store.append(
                    connection,
                    access,
                    prepared,
                    commit_id=uuid4(),
                    correlation_id=identity,
                    expected_seq={scope: sequence},
                )
                await facts.project(connection, event, fixed)
                accepted = await store.accept(
                    connection,
                    self.registry,
                    Caller(actor, "domain", frozenset({scope}), frozenset({"accept"})),
                    entry_name=action,
                    scope_kind=scope[0],
                    scope_id=domain_id,
                    acceptance_key=str(identity),
                    input_ref=artifact_ref(input_id),
                    seconds=300,
                    basis_refs=[subject, *refs],
                    ai_config_ref=run_id,
                )
                await ai_store.pin(connection, accepted, config)
        return AnalysisAcceptance(request_ref=identity, operation_run_id=run_id)

    async def input(self, run: RunInput) -> facts.AnalysisArtifact:
        async with self.engine.begin() as connection:
            work = await store.active(connection, self.registry, run, "step")
            return await self._artifact(connection, work.scope_id, UUID(run.input_ref.id))

    async def finish(self, run: RunInput, result: AnalysisOutput, candidate_id: UUID) -> None:
        fixed = await self.input(run)
        proposal = accepted_output(fixed.payload, result)
        assert fixed.command_ref is not None
        request_id = UUID(fixed.command_ref.id)
        identity = uuid5(request_id, "analysis-result")
        reference = artifact_ref(identity)
        template = fixed.payload["action"] == EXTRACT
        receipt = AnalysisReceipt(
            candidate_ref=reference if template else None,
            check_ref=reference,
            proposed_definition=proposal,
            output=result,
        )
        value = facts.AnalysisArtifact(
            artifact_id=identity,
            domain_id=fixed.domain_id,
            kind="definition_candidate" if template else "classification_check",
            input_ref=run.input_ref,
            definition_refs=fixed.definition_refs,
            payload=receipt.model_dump(mode="json"),
            rule_ref=Ref(owner="domain", type="rules", id="intake-analysis", version=1),
            model_call_ref=Ref(owner="ai", type="candidate", id=str(candidate_id)),
            command_ref=fixed.command_ref,
            created_at=datetime.now(UTC),
        )
        actor = Ref(owner="domain", type="service", id="content-analysis")
        access, draft = self._prepare(
            value,
            facts.TEMPLATE if template else facts.CLASSIFIED,
            fixed.input_ref,
            actor,
            request_id,
        )
        prepared = await self.attachments.prepare(self.event_store, access, (draft,))
        async with self.engine.begin() as connection:
            work = await store.lock_owned(connection, self.registry, run.execution_id)
            if work.state == "completed":
                return
            await store.active(connection, self.registry, run, "finish")
            scope = ("domain", value.domain_id)
            sequence = await lock_scope_sequence(connection, *scope)
            (event,) = await self.event_store.append(
                connection,
                access,
                prepared,
                commit_id=uuid4(),
                correlation_id=request_id,
                expected_seq={scope: sequence},
            )
            await facts.project(connection, event, value)
            await commands.complete(connection, self.registry, run, reference)

    async def receipt(
        self,
        principal: UUID,
        _session: UUID,
        query: ReceiptQuery,
    ) -> ReceiptView[AnalysisReceipt]:
        identity = uuid5(query.resource_id, f"{query.action}:{principal}:{query.request_id}")
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT state,result_ref,error FROM domain.command_receipt "
                        "WHERE receipt_id=:id"
                    ),
                    {"id": identity},
                )
            ).one_or_none()
            if row is None:
                return ReceiptView[AnalysisReceipt](receipt_state="not_found")
            if row.state != "completed":
                return ReceiptView[AnalysisReceipt](
                    receipt_state="accepted" if row.state == "accepted" else "rejected",
                    receipt_ref=identity,
                    execution_ref=uuid5(identity, "execution"),
                    error=ErrorDetail.model_validate(row.error) if row.error else None,
                )
            value = await self._artifact(connection, query.resource_id, UUID(row.result_ref["id"]))
        return ReceiptView[AnalysisReceipt](
            receipt_state="completed",
            receipt_ref=identity,
            result=AnalysisReceipt.model_validate_json(canonical_json(value.payload)),
        )
