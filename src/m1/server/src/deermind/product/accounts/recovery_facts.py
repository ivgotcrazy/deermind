"""密码重置的事实只记录核实依据和凭据代次，绝不记录密码或散列。"""

from uuid import UUID

from deermind.abstractions.events import EventDraft, EventPayload, EventRegistration, Ref
from pydantic import Field


class AccountRecovered(EventPayload):
    account_id: UUID
    verification_ref: Ref
    credential_revision: int = Field(ge=2)


def validate_recovery(draft: EventDraft, payload: EventPayload) -> None:
    if (
        not isinstance(payload, AccountRecovered)
        or payload.records
        or payload.account_id != draft.scope_id
        or draft.owner_ref != Ref(owner="product", type="account", id=str(payload.account_id))
    ):
        raise ValueError("Recovery event does not match its account")


RECOVERED = EventRegistration(
    "AccountRecovered",
    2,
    "product",
    "account",
    AccountRecovered,
    validate_recovery,
)
