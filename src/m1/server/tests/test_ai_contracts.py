"""AI底座输入及事实合同检查；不访问模型、不消耗真实调用额度。"""

import hashlib
import unittest
from datetime import UTC, datetime
from uuid import uuid4

from deermind.foundation.ai.contracts import Budget, ExecutionConfig, ModelProfile, PurposeBinding
from deermind.foundation.ai.execution import AIRejected
from deermind.foundation.ai.facts import AIEvent, validate
from deermind.foundation.ai.records import ConfigurationFact, ModelRequestFact
from deermind.foundation.system.events.contracts import EventDraft, FactRecord, InlineContent, Ref
from deermind.foundation.system.events.store import canonical_json
from deermind.infrastructure.ai.models import checked_response
from pydantic import ValidationError
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.tools import ToolDefinition


class AIContractTests(unittest.TestCase):
    def test_cached_response_cannot_bypass_tool_check(self) -> None:
        """新响应、缓存响应共用检查：未知工具及重复位置均不得执行。"""
        parameters = ModelRequestParameters(function_tools=[ToolDefinition(name="lookup")])
        for response in (
            ModelResponse(parts=[ToolCallPart("delete_everything", {}, tool_call_id="one")]),
            ModelResponse(
                parts=[
                    ToolCallPart("lookup", {}, tool_call_id="same"),
                    ToolCallPart("lookup", {}, tool_call_id="same"),
                ]
            ),
        ):
            with self.assertRaises(AIRejected):
                checked_response(response, parameters)

    """保证配置不带密钥、预算有限、事件范围及未知用量有明确边界。"""

    def test_configuration_rejects_secrets_and_invalid_budget(self) -> None:
        """配置只存凭据引用；隐式无限额度、额外字段和URL凭据都拒绝。"""
        profile = ModelProfile(
            connection_ref=Ref(owner="ai", type="connection", id="fixture", revision=1),
            profile_ref=Ref(owner="ai", type="profile", id="fixture", revision=1),
            adapter="openai_chat",
            base_url="https://example.invalid/v1",
            credential_ref="fixture-key",
            model="fixture-model",
            thinking="disabled",
            temperature=0,
        )
        for extra in ({"api_key": "test-secret"}, {"base_url": "https://secret@example.invalid"}):
            with self.subTest(fields=list(extra)), self.assertRaises(ValidationError):
                ModelProfile.model_validate({**profile.model_dump(), **extra})
        budget = Budget(
            max_model_requests=2,
            max_tool_attempts=0,
            max_repairs=1,
            max_input_tokens=128,
            max_output_tokens=64,
            max_total_tokens=384,
            max_input_bytes=1024,
            max_result_bytes=1024,
            finalize_reserve_seconds=10,
        )
        for change in ({"max_model_requests": 0}, {"max_total_tokens": 100}, {"max_repairs": 2}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                Budget.model_validate({**budget.model_dump(), **change})

    def test_configuration_fact_matrix_hash_and_scope(self) -> None:
        """完整配置才能记入当前工作事实；错hash、错范围和重复正文不能入库。"""
        execution_id = uuid4()
        reference = Ref(owner="ai", type="fixture", id="contract", revision=1)
        config = ExecutionConfig(
            revision="fixture-v1",
            purpose_bindings={
                "test": PurposeBinding(
                    contract_ref=reference,
                    prompt_ref=reference,
                    schema_ref=reference,
                    tool_refs=[],
                    profile=ModelProfile(
                        connection_ref=reference,
                        profile_ref=reference,
                        adapter="openai_chat",
                        base_url="https://example.invalid/v1",
                        credential_ref="fixture-key",
                        model="fixture-model",
                        thinking="disabled",
                        temperature=0,
                    ),
                )
            },
            budget=Budget(
                max_model_requests=2,
                max_tool_attempts=0,
                max_repairs=1,
                max_input_tokens=128,
                max_output_tokens=64,
                max_total_tokens=384,
                max_input_bytes=1024,
                max_result_bytes=1024,
                finalize_reserve_seconds=10,
            ),
        )
        fact = ConfigurationFact(
            execution_id=execution_id,
            config_revision=config.revision,
            config_hash=hashlib.sha256(
                canonical_json(config.model_dump(mode="json")).encode()
            ).hexdigest(),
            config=config.model_dump(mode="json"),
            created_at=datetime.now(UTC),
        )
        subject = Ref(owner="ai", type="configuration", id=str(execution_id))
        record = FactRecord(
            record_id="config",
            record_type="ai.execution_configs",
            schema_version=1,
            content=InlineContent(storage="inline", value=fact.model_dump(mode="json")),
        )
        payload = AIEvent(
            records=[record], subject_ref=subject, outcome="recorded", reason_code=None
        )
        draft = EventDraft(
            uuid4(),
            "AIConfigurationPinned",
            1,
            "execution",
            execution_id,
            subject,
            payload.model_dump(mode="json"),
            "fixture-request",
        )
        validate(draft, payload)
        for changed in (
            fact.model_copy(update={"config_hash": "0" * 64}),
            fact.model_copy(update={"execution_id": uuid4()}),
        ):
            invalid = record.model_copy(
                update={
                    "content": InlineContent(
                        storage="inline", value=changed.model_dump(mode="json")
                    )
                }
            )
            with self.assertRaises(ValueError):
                validate(draft, payload.model_copy(update={"records": [invalid]}))
        with self.assertRaises(ValueError):
            validate(draft, payload.model_copy(update={"records": [record, record]}))

    def test_unknown_usage_is_not_zero(self) -> None:
        """未知响应保留预约；只有完整usage才能结算实际token。"""
        request = ModelRequestFact(
            call_id=uuid4(),
            attempt_id=uuid4(),
            request_ordinal=1,
            transport_attempt=1,
            model="fixture-model",
            request_ref=Ref(owner="ai", type="request", id="fixture"),
            reserved_input_tokens=128,
            reserved_output_tokens=64,
            actual_input_tokens=None,
            actual_output_tokens=None,
            usage_state="unknown",
            provider_request_id=None,
            outcome="unknown",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            response_ref=None,
        )
        for change in (
            {"actual_input_tokens": 0, "actual_output_tokens": 0},
            {"usage_state": "known"},
            {"finished_at": None},
        ):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                ModelRequestFact.model_validate({**request.model_dump(), **change})
