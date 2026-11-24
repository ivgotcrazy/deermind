"""E01-15模型调用合同；默认仅用替身，真实模型验证另行显式启用。"""

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from ai_fixture import AIWorkflow, Fixture, Output
from deermind.abstractions.ai.calls import AIRejected
from deermind.abstractions.ai.contracts import ModelProfile, PromptCallInput
from deermind.abstractions.events import Ref
from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.ai import store as ai_store
from deermind.foundation.ai.prompts import PromptLibrary, PromptSource
from deermind.foundation.ai.records import CandidateFact
from deermind.foundation.system.executions import commands
from deermind.foundation.system.executions import store as executions
from deermind.infrastructure.ai.agent import build_agent
from deermind.infrastructure.ai.execution import Activities
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.files.local import LocalFiles
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage
from sqlalchemy import text
from temporalio.client import Client
from temporalio.worker import Worker
from test_database import DatabaseTestCase


class AICallTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    @asynccontextmanager
    async def fixture(self) -> AsyncGenerator[Fixture]:
        engine = application_engine(self.app)
        files = LocalFiles(Path(self.directory.name), backend="local")
        try:
            yield Fixture(engine, files, "e0115-" + uuid4().hex)
        finally:
            await engine.dispose()

    def test_fixed_configuration_input_conflict_and_unknown_usage(self) -> None:
        """配置固定、调用防重、未知保留预约，恢复/重复调用不能清零。"""
        asyncio.run(self.configuration_and_usage())

    def test_restored_call_reads_the_accepted_prompt_version(self) -> None:
        """切换默认版本后，旧任务复用同一调用与候选，新任务读取新版。"""
        asyncio.run(self.prompt_version())

    async def prompt_version(self) -> None:
        async with self.fixture() as fixture:
            first = Ref(owner="interaction", type="prompt", id="fixture", version=1)
            second = first.model_copy(update={"version": 2})

            def select_prompt(ref: Ref) -> None:
                binding = fixture.config.purpose_bindings["ai_test"]
                fixture.config = fixture.config.model_copy(
                    update={
                        "purpose_bindings": {
                            "ai_test": binding.model_copy(update={"prompt_ref": ref})
                        }
                    }
                )

            select_prompt(first)
            async with fixture.calls.engine.begin() as connection:
                old = await fixture.accept(connection, "old-prompt")
            handle = await fixture.calls.prepare(old)
            candidate = await fixture.calls.candidate(handle, {"answer": "five quarters"})

            root = Path(self.directory.name)
            for ref, instructions in ((first, old.instructions), (second, "New prompt.")):
                directory = root / "prompts" / ref.id / f"v{ref.version}"
                directory.mkdir(parents=True)
                (directory / "instructions.md").write_text(instructions + "\n", encoding="utf-8")
            with patch("deermind.foundation.ai.prompts.files", return_value=root):
                fixture.calls.prompts = PromptLibrary([PromptSource("fixture", second)])
                select_prompt(second)
                async with fixture.calls.engine.begin() as connection:
                    new = await fixture.accept(connection, "new-prompt")
                    await commands.fail(connection, fixture.registry, old.run, fixture.reference)
                    restored = await commands.retry(
                        connection,
                        fixture.registry,
                        fixture.caller(),
                        old.run.execution_id,
                        request_id="restore-old-prompt",
                        seconds=300,
                    )
                    assert restored.active_attempt_id is not None
                    attempt = await executions.attempt(connection, restored.active_attempt_id)
                    run = old.run.model_copy(
                        update={
                            "attempt_id": attempt.attempt_id,
                            "deadline_at": attempt.deadline_at,
                        }
                    )
                    await commands.start(connection, fixture.registry, run)
                for request, reference, instructions in (
                    (old.model_copy(update={"run": run}), first, old.instructions),
                    (new, second, "New prompt."),
                ):
                    packaged = PromptCallInput(
                        **request.model_dump(exclude={"instructions"}),
                        prompt_parts=["instructions"],
                    )
                    saved = await fixture.calls.prepare(packaged)
                    self.assertEqual(saved.binding.prompt_ref, reference)
                    self.assertEqual(saved.input.instructions, instructions)
                    if reference == first:
                        self.assertEqual(saved.call_id, handle.call_id)
                        self.assertEqual(saved.candidate_ref, candidate)
                    else:
                        self.assertIsNone(saved.candidate_ref)

    async def configuration_and_usage(self) -> None:
        async with self.fixture() as fixture:
            async with fixture.calls.engine.begin() as connection:
                incoming = await fixture.accept(connection, "ledger")
            handle = await fixture.calls.prepare(incoming)
            again = await fixture.calls.prepare(incoming)
            self.assertEqual(again.call_id, handle.call_id)
            self.assertEqual(again.attempt_id, handle.attempt_id)
            with self.assertRaisesRegex(AIRejected, "input_conflict"):
                await fixture.calls.prepare(
                    incoming.model_copy(update={"prompt": "different input"})
                )
            request = await fixture.calls.reserve(handle, 1, 1, fixture.reference, 20, repair=False)
            await fixture.calls.settle(
                handle,
                request,
                response_ref=None,
                actual_usage=None,
                provider_id=None,
                error_code="connection_lost",
            )
            await fixture.calls.settle(
                handle,
                request,
                response_ref=None,
                actual_usage=None,
                provider_id=None,
                error_code="connection_lost",
            )
            async with fixture.calls.engine.connect() as connection:
                usage = (
                    (await connection.execute(text("SELECT * FROM ai.execution_usage")))
                    .mappings()
                    .one()
                )
                self.assertEqual((usage["request_count"], usage["unknown_request_count"]), (1, 1))
                self.assertEqual(usage["reserved_input_tokens"], 20)
                self.assertEqual(usage["reserved_output_tokens"], 512)
                saved = await ai_store.configuration(connection, incoming.run.execution_id)
                self.assertEqual(saved, fixture.config)
            with self.assertRaisesRegex(AIRejected, "input_conflict"):
                changed = handle.model_copy(
                    update={"budget": handle.budget.model_copy(update={"max_model_requests": 100})}
                )
                await fixture.calls.reserve(changed, 2, 1, fixture.reference, 20, repair=False)
            for ordinal in range(2, 5):
                await fixture.calls.reserve(handle, ordinal, 1, fixture.reference, 20, repair=False)
            with self.assertRaisesRegex(AIRejected, "budget_exhausted"):
                await fixture.calls.reserve(handle, 5, 1, fixture.reference, 20, repair=False)
            async with fixture.calls.engine.connect() as connection:
                self.assertEqual(
                    await connection.scalar(text("SELECT request_count FROM ai.execution_usage")), 4
                )
            async with fixture.calls.engine.begin() as connection:
                await commands.fail(connection, fixture.registry, incoming.run, fixture.reference)
                restored = await commands.retry(
                    connection,
                    fixture.registry,
                    fixture.caller(),
                    incoming.run.execution_id,
                    request_id="retry",
                    seconds=300,
                )
                assert restored.active_attempt_id is not None
                attempt = await executions.attempt(connection, restored.active_attempt_id)
                run = incoming.run.model_copy(
                    update={"attempt_id": attempt.attempt_id, "deadline_at": attempt.deadline_at}
                )
                await commands.start(connection, fixture.registry, run)
            recovered = await fixture.calls.prepare(incoming.model_copy(update={"run": run}))
            self.assertEqual(recovered.call_id, handle.call_id)
            self.assertNotEqual(recovered.attempt_id, handle.attempt_id)
            with self.assertRaisesRegex(AIRejected, "budget_exhausted"):
                await fixture.calls.reserve(recovered, 1, 1, fixture.reference, 20, repair=False)

    def test_candidate_atomicity_and_stop(self) -> None:
        """候选和调用完成同事务；停止后不能接收迟到候选。"""
        asyncio.run(self.candidate_and_stop())

    async def candidate_and_stop(self) -> None:
        async with self.fixture() as fixture:
            async with fixture.calls.engine.begin() as connection:
                incoming = await fixture.accept(connection, "candidate")
            handle = await fixture.calls.prepare(incoming)
            with patch.object(
                ai_store, "apply_ai_events", side_effect=RuntimeError("projection fault")
            ):
                with self.assertRaisesRegex(RuntimeError, "projection fault"):
                    await fixture.calls.candidate(handle, {"answer": "five quarters"})
            async with fixture.calls.engine.connect() as connection:
                self.assertEqual(
                    await connection.scalar(text("SELECT count(*) FROM ai.ai_candidates")), 0
                )
                self.assertEqual(
                    await connection.scalar(
                        text(
                            "SELECT count(*) FROM runtime.events "
                            "WHERE event_type='AICandidatePrepared'"
                        )
                    ),
                    0,
                )
            identity = await fixture.calls.candidate(handle, {"answer": "five quarters"})
            replay = await fixture.calls.prepare(incoming)
            self.assertEqual(replay.candidate_ref, identity)
            async with fixture.calls.engine.connect() as connection:
                candidate = await ai_store.load(
                    connection, "ai.ai_candidates", CandidateFact, {"candidate_id": identity}
                )
                self.assertIsNotNone(candidate)
                self.assertEqual(
                    await connection.scalar(text("SELECT count(*) FROM ai.ai_candidates")), 1
                )
            async with fixture.calls.engine.begin() as connection:
                other = await fixture.accept(connection, "stop")
            stopped = await fixture.calls.prepare(other)
            async with fixture.calls.engine.begin() as connection:
                await commands.cancel(
                    connection,
                    fixture.registry,
                    fixture.caller(),
                    other.run.execution_id,
                    request_id="stop-request",
                )
            with self.assertRaises(ValueError):
                await fixture.calls.candidate(stopped, {"answer": "late"})

    def test_tool_grants_current_permission_and_receipt(self) -> None:
        """工具三方授权，重复动作复用已存结果，当前资格撤销即拒绝。"""
        asyncio.run(self.tool_checks())

    async def tool_checks(self) -> None:
        async with self.fixture() as fixture:
            async with fixture.calls.engine.begin() as connection:
                incoming = await fixture.accept(connection, "tools")
            handle = await fixture.calls.prepare(incoming)
            first = await fixture.tools.invoke(handle, "lookup", {"query": "value"}, 1, 1)
            again = await fixture.tools.invoke(handle, "lookup", {"query": "value"}, 1, 1)
            self.assertEqual(first, again)
            self.assertEqual(fixture.tool_effects, 1)
            with self.assertRaisesRegex(AIRejected, "forbidden"):
                await fixture.tools.invoke(handle, "delete_everything", {}, 1, 2)
            self.assertEqual(fixture.tool_effects, 1)
            fixture.allowed = False
            with self.assertRaises(PermissionError):
                await fixture.tools.invoke(handle, "lookup", {"query": "value"}, 2, 1)

    def test_official_temporal_structured_repair_and_cached_candidate(self) -> None:
        """真实Temporal运行官方集成：结构错误修正一次，已存候选不再调用模型。"""
        asyncio.run(self.temporal_repair())

    async def temporal_repair(self) -> None:
        async with self.fixture() as fixture:
            requests: list[str] = []
            keys = ["first-test-key"]

            async def response(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
                if len(requests) == 1:
                    raise ConnectionError("synthetic-secret-must-not-leak")
                name = "submit_candidate"
                if len(requests) == 2:
                    name, output = "lookup", {"query": "value"}
                else:
                    output = (
                        {"wrong": "shape"} if len(requests) == 3 else {"answer": "five quarters"}
                    )
                return ModelResponse(
                    parts=[ToolCallPart(name, output)],
                    usage=RequestUsage(input_tokens=50, output_tokens=10),
                    model_name="fixture-model",
                )

            def factory(profile: ModelProfile, key: str) -> FunctionModel:
                requests.append(key)
                keys[0] = "rotated-test-key"
                return FunctionModel(response, model_name=profile.model)

            agent = build_agent(
                fixture.purpose, fixture.calls, fixture.tools, lambda _: keys[0], factory=factory
            )
            activities = Activities(fixture.calls, {fixture.reference.model_dump_json(): Output})
            AIWorkflow.agent = agent
            AIWorkflow.__pydantic_ai_agents__ = [agent]
            client = await Client.connect(
                os.environ["M1_TEST_TEMPORAL_ADDRESS"],
                namespace=os.environ["M1_TEST_TEMPORAL_NAMESPACE"],
                plugins=[PydanticAIPlugin()],
            )
            async with fixture.calls.engine.begin() as connection:
                incoming = await fixture.accept(connection, "temporal")
            async with Worker(
                client,
                task_queue=fixture.queue,
                workflows=[AIWorkflow],
                activities=[activities.prepare, activities.save, activities.fail],
            ):
                first = await asyncio.wait_for(
                    client.execute_workflow(
                        AIWorkflow.run,
                        incoming.model_dump_json(),
                        id="ai-test-" + uuid4().hex,
                        task_queue=fixture.queue,
                    ),
                    60,
                )
                second = await asyncio.wait_for(
                    client.execute_workflow(
                        AIWorkflow.run,
                        incoming.model_dump_json(),
                        id="ai-test-" + uuid4().hex,
                        task_queue=fixture.queue,
                    ),
                    60,
                )
            self.assertEqual(first, second)
            self.assertEqual(requests, ["first-test-key"] + ["rotated-test-key"] * 3)
            self.assertEqual(fixture.tool_effects, 1)
            async with fixture.calls.engine.connect() as connection:
                usage = (
                    (await connection.execute(text("SELECT * FROM ai.execution_usage")))
                    .mappings()
                    .one()
                )
                self.assertEqual(usage["request_count"], 4)
                self.assertEqual(usage["repair_count"], 1)
                self.assertEqual(usage["known_input_tokens"], 150)
                self.assertGreater(usage["reserved_input_tokens"], 0)
                self.assertEqual(usage["unknown_request_count"], 1)
                facts = await connection.scalar(
                    text("SELECT string_agg(payload::text,'') FROM runtime.events")
                )
                self.assertNotIn("first-test-key", facts)
                self.assertNotIn("rotated-test-key", facts)
                self.assertNotIn("synthetic-secret-must-not-leak", facts)
