"""显式真实模型验收；合成文字、累计六次上限，默认跳过，绝不打印凭据。"""

import asyncio
import fcntl
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai_fixture import AIWorkflow, Fixture, Output
from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.ai.contracts import ModelProfile
from deermind.foundation.system.events.contracts import Ref
from deermind.infrastructure.ai.agent import build_agent
from deermind.infrastructure.ai.execution import Activities
from deermind.infrastructure.ai.models import provider_model
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.files.local import LocalFiles
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from pydantic_ai.models import Model
from sqlalchemy import text
from temporalio.client import Client
from temporalio.worker import Worker
from test_database import DatabaseTestCase


def reserve_batch(path: Path) -> None:
    """发请求前同步累计；包括结果未知的尝试，重复运行也不能重置批准额度。"""
    with path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        count = len(stream.readlines())
        if count >= 6:
            raise ValueError("Approved live request quota exhausted")
        stream.write(json.dumps({"request": count + 1, "reserved_tokens": 4608}) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


@unittest.skipUnless(os.environ.get("M1_LIVE_AI") == "1", "Real model requires explicit approval")
class LiveAITests(DatabaseTestCase):
    def test_live_candidate_and_no_second_request(self) -> None:
        """真实供应商只用合成算术材料；重复同一调用直接取已存候选。"""
        upgrade(self.migrator)
        asyncio.run(self.run_live())

    async def run_live(self) -> None:
        directory = Path(os.environ["M1_AI_EVIDENCE_DIR"])
        directory.mkdir(parents=True, exist_ok=True)
        if os.environ["DEERMIND_LLM_MODEL"] != "deepseek-flash":
            raise ValueError("Live model differs from approved selection")
        engine = application_engine(self.app)
        try:
            with tempfile.TemporaryDirectory() as files:
                fixture = Fixture(
                    engine, LocalFiles(Path(files), backend="local"), "ai-live-" + uuid4().hex
                )
                binding = fixture.config.purpose_bindings["ai_test"]
                profile = binding.profile.model_copy(
                    update={
                        "model": os.environ["DEERMIND_LLM_MODEL"],
                        "base_url": os.environ["DEERMIND_LLM_BASE_URL"],
                        "credential_ref": "live-test-key",
                    }
                )
                binding = binding.model_copy(update={"profile": profile, "tool_refs": []})
                fixture.config = fixture.config.model_copy(
                    update={
                        "purpose_bindings": {"ai_test": binding},
                        "budget": fixture.config.budget.model_copy(
                            update={
                                "max_model_requests": 6,
                                "max_tool_attempts": 0,
                                "max_input_tokens": 4096,
                                "max_total_tokens": 27648,
                            }
                        ),
                    }
                )

                # SDK供应商类型只在工厂边界动态化，结果仍按固定Schema校验。
                def factory(profile: ModelProfile, key: str) -> Model[Any]:
                    reserve_batch(directory / "live-request-ledger.jsonl")
                    return provider_model(profile, key)

                agent = build_agent(
                    fixture.purpose,
                    fixture.calls,
                    fixture.tools,
                    lambda _: os.environ["DEERMIND_LLM_API_KEY"],
                    factory=factory,
                )
                activities = Activities(
                    fixture.calls, {fixture.reference.model_dump_json(): Output}
                )
                AIWorkflow.agent = agent
                AIWorkflow.__pydantic_ai_agents__ = [agent]
                client = await Client.connect(
                    os.environ["M1_TEST_TEMPORAL_ADDRESS"],
                    namespace=os.environ["M1_TEST_TEMPORAL_NAMESPACE"],
                    plugins=[PydanticAIPlugin()],
                )
                async with engine.begin() as connection:
                    incoming = await fixture.accept(connection, "live")
                incoming = incoming.model_copy(update={"tool_grants": []})
                async with Worker(
                    client,
                    task_queue=fixture.queue,
                    workflows=[AIWorkflow],
                    activities=[activities.prepare, activities.save, activities.fail],
                ):
                    identities: list[str] = []
                    for _ in range(2):
                        identities.append(
                            await asyncio.wait_for(
                                client.execute_workflow(
                                    AIWorkflow.run,
                                    incoming.model_dump_json(),
                                    id="ai-live-" + uuid4().hex,
                                    task_queue=fixture.queue,
                                ),
                                300,
                            )
                        )
                self.assertEqual(identities[0], identities[1])
                async with engine.connect() as connection:
                    usage = dict(
                        (await connection.execute(text("SELECT * FROM ai.execution_usage")))
                        .mappings()
                        .one()
                    )
                    content = await connection.scalar(text("SELECT content FROM ai.ai_candidates"))
                result = await fixture.calls.attachments.read_json(
                    Ref(owner="runtime", type="file", id=content["file_id"]),
                    source=Ref(owner="ai", type="execution", id=str(incoming.run.execution_id)),
                    max_bytes=32768,
                )
                Output.model_validate(result)
                (directory / "live-result.json").write_text(
                    json.dumps(
                        {
                            "input": incoming.prompt,
                            "output": result,
                            "usage": usage,
                            "cached_candidate": identities[0] == identities[1],
                            "model": profile.model,
                            "price": "unknown",
                        },
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    ),
                    encoding="utf-8",
                )
        finally:
            await engine.dispose()
