"""评价定义的管理端 HTTP 入口。"""

from hashlib import sha256
from secrets import compare_digest
from typing import Annotated, Literal
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.entrypoints.api.auth import access
from deermind.entrypoints.api.errors import ERRORS
from deermind.foundation.system.public.errors import RequestError
from deermind.product.public.authentication import SessionView
from deermind.product.public.courses import LearningSpaceService
from deermind.spaces.evaluation.public import (
    BasisView,
    ClaimCommand,
    ClaimDetail,
    ClaimList,
    ClaimReceipt,
    ClaimService,
    EvaluationBasisService,
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


@router.get(
    "/spaces/{scope_id}/basis",
    response_model=BasisView,
    response_model_exclude_none=True,
    responses=ERRORS,
    operation_id="evaluation_read_basis",
)
async def read_basis(
    request: Request,
    response: Response,
    scope_id: UUID,
    view: Literal["target", "belief", "evidence", "event", "processing"],
    result_id: UUID | None = None,
    item_id: UUID | None = None,
    evidence_id: UUID | None = None,
    event_id: UUID | None = None,
    snapshot_id: UUID | None = None,
    claim_id: UUID | None = None,
    claim_revision: Annotated[int | None, Query(ge=1)] = None,
    method_id: UUID | None = None,
    method_version: Annotated[int | None, Query(ge=1)] = None,
    aspect_code: Literal["independent", "understanding", "transfer", "retention"] | None = None,
    cursor: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    expected: ExpectedSession = None,
) -> BasisView:
    auth, config = access(request)
    session = await auth.session(request.cookies.get(config.cookie_name), expected)
    if expected is None:
        raise RequestError(403, "forbidden", "请使用有效的会话。")
    response.headers["Cache-Control"] = "no-store"
    spaces: LearningSpaceService = request.app.state.course_spaces
    await spaces.current_adoption(session.account, scope_id)
    service: EvaluationBasisService = request.app.state.evaluation_basis
    binding = sha256(
        canonical_json(
            [
                str(session.account.account_id),
                str(scope_id),
                view,
                *[
                    str(value)
                    for value in (
                        result_id,
                        item_id,
                        event_id,
                        snapshot_id,
                        claim_id,
                        claim_revision,
                        method_id,
                        method_version,
                        aspect_code,
                    )
                ],
            ]
        ).encode()
    ).hexdigest()[:24]
    after = _basis_cursor(cursor, binding)
    if view == "target" and result_id and item_id:
        result = await service.target(scope_id, result_id, item_id, after, limit)
    elif view == "evidence" and evidence_id:
        return await service.evidence(scope_id, evidence_id, event_id)
    elif view == "event" and event_id:
        if session.account.role != "admin":
            raise RequestError(403, "forbidden", "只有管理员可从事件查看相关证据。")
        result = await service.from_event(scope_id, event_id, after, limit)
    elif view == "processing" and event_id:
        return await service.processing(scope_id, event_id)
    elif view == "belief" and (
        snapshot_id and claim_id and claim_revision and method_id and method_version and aspect_code
    ):
        result = await service.belief(
            scope_id,
            snapshot_id,
            claim_id,
            claim_revision,
            method_id,
            method_version,
            aspect_code,
            after,
            limit,
        )
    else:
        raise RequestError(400, "invalid_request", "缺少本次评价查询所需的引用。")
    if result.next_cursor:
        result = result.model_copy(update={"next_cursor": f"{binding}.{result.next_cursor}"})
    return result


def _basis_cursor(cursor: str | None, binding: str) -> UUID | None:
    if cursor is None:
        return None
    prefix, _, value = cursor.partition(".")
    if not compare_digest(prefix.encode(), binding.encode()):
        raise RequestError(400, "invalid_request", "续页位置与本次评价查询不符。")
    try:
        return UUID(value)
    except ValueError as error:
        raise RequestError(400, "invalid_request", "续页位置无效。") from error
