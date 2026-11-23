"""Interaction 只发布已固定采用依据的供题请求。"""

from deermind.abstractions.events import EventDraft, EventPayload, EventRegistration
from deermind.abstractions.task_supply import REQUESTED, TaskSupplyRequested


def _validate(draft: EventDraft, payload: EventPayload) -> None:
    if (
        not isinstance(payload, TaskSupplyRequested)
        or payload.request_ref != draft.owner_ref
        or payload.records
        or payload.task_ref.owner != "domain"
        or payload.task_ref.type != "task"
        or payload.task_ref.version is None
        or not payload.allowed_method_refs
        or not payload.method_source_refs
    ):
        raise ValueError("Supply request needs a fixed task and permitted chapter methods")
    if any(
        reference.owner != "domain" or reference.type != "solution" or reference.version is None
        for reference in payload.allowed_method_refs
    ):
        raise ValueError("Supply request method versions are invalid")


REGISTRATION = EventRegistration(
    REQUESTED, 1, "interaction", "learning_space", TaskSupplyRequested, _validate, {}
)
