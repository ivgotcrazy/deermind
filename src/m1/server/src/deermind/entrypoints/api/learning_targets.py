"""Learning target commands and immutable revision queries."""

from typing import Annotated
from uuid import UUID

from deermind.entrypoints.api.errors import ERRORS
from deermind.entrypoints.api.evaluation import CsrfToken, ExpectedSession, admin_session
from deermind.product.public.learning_targets import (
    LearningTargets,
    TargetCommand,
    TargetDetail,
    TargetList,
    TargetReceipt,
)
from fastapi import APIRouter, Query, Request, Response

router = APIRouter(prefix="/api/m1/learning-targets", tags=["learning-targets"])


@router.get("", response_model=TargetList, responses=ERRORS, operation_id="product_list_targets")
async def list_targets(
    request: Request,
    response: Response,
    textbook_id: UUID,
    cursor: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    expected: ExpectedSession = None,
) -> TargetList:
    session = await admin_session(request, response, expected)
    service: LearningTargets = request.app.state.learning_targets
    return await service.list_targets(session.account.account_id, textbook_id, cursor, limit)


@router.get(
    "/{target_id}",
    response_model=TargetDetail,
    responses=ERRORS,
    operation_id="product_read_target",
)
async def read_target(
    request: Request,
    response: Response,
    target_id: UUID,
    revision: Annotated[int | None, Query(ge=1, le=2**63 - 1)] = None,
    expected: ExpectedSession = None,
) -> TargetDetail:
    await admin_session(request, response, expected)
    service: LearningTargets = request.app.state.learning_targets
    return await service.detail(target_id, revision)


@router.post("", response_model=TargetReceipt, responses=ERRORS, operation_id="product_save_target")
async def save_target(
    request: Request,
    response: Response,
    body: TargetCommand,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> TargetReceipt:
    session = await admin_session(request, response, expected, csrf, writing=True)
    service: LearningTargets = request.app.state.learning_targets
    return await service.save(session.account.account_id, body)
