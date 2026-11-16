"""密码重置的事实只记录核实依据和凭据代次，绝不记录密码或散列。"""

from uuid import UUID

from deermind.foundation.system.events.contracts import (
    EventDraft,
    EventPayload,
    EventRegistration,
    Ref,
)
from deermind.foundation.system.events.reading import EventFact, ReadAccess, ReadGrant, ReadPolicy
from deermind.product.accounts.auth_facts import record_only
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
    "product.auth_audit.v1",
    record_only,
)


def recovery_read(access: ReadAccess, event: EventFact) -> ReadGrant | None:
    if access.maintenance_ref is None:
        return None
    return ReadGrant(
        {}, frozenset({"account_id", "verification_ref", "credential_revision"}), "账号凭据已重置"
    )


RECOVERY_READ_POLICY = ReadPolicy(
    "AccountRecovered", 2, "runtime", "projection_rebuild", recovery_read
)
