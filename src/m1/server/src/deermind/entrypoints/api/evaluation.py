"""评价定义的管理端 HTTP 入口。"""

from secrets import compare_digest
from typing import Annotated
from uuid import UUID

from deermind.entrypoints.api.auth import access
from deermind.entrypoints.api.errors import ERRORS
from deermind.foundation.system.public.errors import RequestError
from deermind.product.public.authentication import SessionView
from deermind.spaces.evaluation.public import (
    ClaimCommand,
    ClaimDetail,
    ClaimList,
    ClaimReceipt,
    ClaimService,
)
from fastapi import APIRouter, Header, Query, Request, Response

router = APIRouter(prefix="/api/m1/evaluation", tags=["evaluation"])
ExpectedSession = Annotated[str | None, Header(alias="X-Expected-Session")]
CsrfToken = Annotated[str | None, Header(alias="X-CSRF-Token")]


async def admin_session(
    request: Request,
    response: Response,
    expected: str | None,
    csrf: str | None = None,
    *,
    writing: bool = False,
) -> SessionView:
    auth, config = access(request, writing=writing)
    session = await auth.session(request.cookies.get(config.cookie_name), expected)
    if (
        expected is None
        or session.account.role != "admin"
        or (
            writing
            and (csrf is None or not compare_digest(csrf.encode(), session.csrf_token.encode()))
        )
    ):
        raise RequestError(403, "forbidden", "请使用有效的管理员会话。")
    response.headers["Cache-Control"] = "no-store"
    return session


@router.get(
    "/claims", response_model=ClaimList, responses=ERRORS, operation_id="evaluation_list_claims"
)
async def list_claims(
    request: Request,
    response: Response,
    domain_id: UUID,
    task_id: UUID | None = None,
    name: Annotated[str, Query(max_length=160)] = "",
    cursor: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    expected: ExpectedSession = None,
) -> ClaimList:
    session = await admin_session(request, response, expected)
    service: ClaimService = request.app.state.claims
    return await service.list_claims(
        session.account.account_id, domain_id, task_id, name.strip(), cursor, limit
    )


@router.get(
    "/claims/{claim_id}",
    response_model=ClaimDetail,
    responses=ERRORS,
    operation_id="evaluation_read_claim",
)
async def read_claim(
    request: Request,
    response: Response,
    claim_id: UUID,
    revision: Annotated[int | None, Query(ge=1, le=2**63 - 1)] = None,
    expected: ExpectedSession = None,
) -> ClaimDetail:
    await admin_session(request, response, expected)
    service: ClaimService = request.app.state.claims
    return await service.detail(claim_id, revision)


@router.post(
    "/claim-commands",
    response_model=ClaimReceipt,
    responses=ERRORS,
    operation_id="evaluation_save_claim",
)
async def save_claim(
    request: Request,
    response: Response,
    body: ClaimCommand,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> ClaimReceipt:
    session = await admin_session(request, response, expected, csrf, writing=True)
    service: ClaimService = request.app.state.claims
    return await service.save(session.account.account_id, body)
