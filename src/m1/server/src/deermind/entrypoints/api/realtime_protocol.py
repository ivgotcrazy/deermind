"""WebSocket 传输信封。业务动作仍由各自的处理方校验。"""

import json
from typing import Annotated, Literal

from deermind.abstractions.events import Ref
from deermind.foundation.system.public.errors import ErrorDetail
from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr, TypeAdapter

SUBPROTOCOL = "deermind.v1"
MESSAGE_BYTES = 64 * 1024
Id = Annotated[str, Field(min_length=1)]

ACTION_RESOURCES = {
    "learning.input": "learning_space",
    "learning.answer": "learning_space",
    "learning.activity_action": "learning_space",
    "learning.proactive_response": "learning_space",
    "learning.presentation": "learning_space",
    "material.input": "material_import",
}
RESOURCE_VIEWS = {
    "learning_space": frozenset({"conversation", "activity_tree", "goal", "events"}),
    "material_import": frozenset({"messages", "contents", "candidates", "intake"}),
}


class Frame(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, strict=True, frozen=True)


class Resource(Frame):
    kind: Id
    id: Id


class Hello(Frame):
    type: Literal["hello"] = "hello"
    session_id: Id
    csrf_token: SecretStr


class Ready(Frame):
    type: Literal["ready"] = "ready"
    connection_id: Id
    server_time: str


class Command(Frame):
    type: Literal["command"] = "command"
    frame_id: Id
    request_id: Id
    action: Id
    resource: Resource
    payload: dict[str, JsonValue]

    def business_size(self) -> int:
        normal = self.model_dump()
        normal["frame_id"] = self.request_id
        # 禁止将 NaN、Infinity 或无法表示的数字悄悄改写为 null。
        data = json.dumps(normal, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        return len(data.encode("utf-8"))


class CommandResult(Frame):
    state: Literal["accepted", "completed"]
    owner_receipt_ref: Id
    execution_ref: Id | None = None
    result_refs: list[Ref] = Field(default_factory=lambda: list[Ref]())


class Receipt(CommandResult):
    type: Literal["receipt"] = "receipt"
    frame_id: Id
    request_id: Id


class Error(Frame):
    type: Literal["error"] = "error"
    frame_id: str | None = None
    request_id: str | None = None
    error: ErrorDetail
    acceptance: Literal["not_accepted", "unknown"] = "not_accepted"


class WatchFields(Frame):
    frame_id: Id
    watch_id: Id
    resource: Resource
    views: list[Id] = Field(min_length=1)


class Watch(WatchFields):
    type: Literal["watch"] = "watch"


class WatchReady(WatchFields):
    type: Literal["watch_ready"] = "watch_ready"


class Unwatch(Frame):
    type: Literal["unwatch"] = "unwatch"
    frame_id: Id
    watch_id: Id


class UnwatchReady(Frame):
    type: Literal["unwatch_ready"] = "unwatch_ready"
    frame_id: Id
    watch_id: Id


class Changed(Frame):
    type: Literal["changed"] = "changed"
    watch_id: Id
    resource: Resource
    views: list[Id]
    request_id: Id | None = None


class Heartbeat(Frame):
    type: Literal["ping", "pong"]
    frame_id: Id


class ResyncRequired(Frame):
    type: Literal["resync_required"] = "resync_required"
    watch_id: Id | None
    reason: str


type Incoming = Annotated[
    Hello | Command | Watch | Unwatch | Heartbeat,
    Field(discriminator="type"),
]
INCOMING = TypeAdapter[Incoming](Incoming)
