"""调用方提供用途、材料和权限；AI底座只执行登记的能力和有限预算。"""

from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from deermind.foundation.system.events.contracts import FactModel, NonEmpty, Ref
from deermind.foundation.system.executions.contracts import RunInput
from pydantic import Field, model_validator

Positive = Annotated[int, Field(gt=0)]
NonNegative = Annotated[int, Field(ge=0)]


class Budget(FactModel):
    """所有数值显式给出；真实外发、工具失败和修正均消耗原工作的额度。"""

    max_model_requests: Positive
    max_tool_attempts: NonNegative
    max_repairs: Annotated[int, Field(ge=0, le=1)]
    max_input_tokens: Positive
    max_output_tokens: Annotated[int, Field(gt=0, le=8192)]
    max_total_tokens: Positive
    max_input_bytes: Positive
    max_result_bytes: Positive
    finalize_reserve_seconds: Positive

    @model_validator(mode="after")
    def total_covers_one_request(self) -> "Budget":
        if self.max_total_tokens < self.max_input_tokens + self.max_output_tokens:
            raise ValueError("Total budget must cover one maximum request")
        if self.max_repairs >= self.max_model_requests:
            raise ValueError("Repair requires a remaining model request")
        return self


class ModelProfile(FactModel):
    """固定连接和模型设置，不保存密钥或任意可透传的供应商参数。"""

    connection_ref: Ref
    profile_ref: Ref
    adapter: Literal["openai_chat"]
    base_url: NonEmpty
    credential_ref: NonEmpty
    model: NonEmpty
    thinking: Literal["disabled"]
    temperature: Literal[0]

    @model_validator(mode="after")
    def controlled_address(self) -> "ModelProfile":
        # 只接受装配配置；此检查还阻止把认证信息放进URL后进入事实/历史。
        address = urlsplit(self.base_url)
        if (
            address.scheme != "https"
            or not address.hostname
            or address.username is not None
            or address.password is not None
            or address.query
            or address.fragment
        ):
            raise ValueError("Model endpoint requires HTTPS and no embedded credentials")
        return self


class PurposeBinding(FactModel):
    """受理时固定所需用途；运行中只能缩小工具集合，不能替换提示合同。"""

    contract_ref: Ref
    prompt_ref: Ref
    schema_ref: Ref
    tool_refs: list[Ref]
    profile: ModelProfile


class ExecutionConfig(FactModel):
    """工作配置快照；恢复沿用同一份配置，凭据每次从当前秘密存储取得。"""

    revision: NonEmpty
    purpose_bindings: dict[str, PurposeBinding]
    budget: Budget

    @model_validator(mode="after")
    def nonempty_bindings(self) -> "ExecutionConfig":
        if not self.purpose_bindings or any(not key.strip() for key in self.purpose_bindings):
            raise ValueError("An AI work requires registered purposes")
        return self


class CallInput(FactModel):
    """Operation组装好的输入；工具集合是程序授予，不从模型正文解析。"""

    run: RunInput
    step_key: NonEmpty
    call_key: NonEmpty
    purpose: NonEmpty
    instructions: NonEmpty
    prompt: NonEmpty
    material_refs: list[Ref]
    tool_grants: list[Ref]


class CallHandle(FactModel):
    """可进入执行历史的调用身份；只含非秘密配置，凭据在外发前取得。"""

    input: CallInput
    call_id: UUID
    attempt_id: UUID
    binding: PurposeBinding
    budget: Budget
    candidate_ref: UUID | None
