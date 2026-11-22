"""管理员领域列表、新建和选中详情的 HTTP 入口。"""

from secrets import compare_digest
from typing import Annotated
from uuid import UUID

from deermind.entrypoints.api.auth import access
from deermind.entrypoints.api.errors import ERRORS
from deermind.product.public.authentication import AuthError, SessionView
from deermind.spaces.domain.public import (
    CreateDomainRequest,
    CreateDomainResponse,
    DomainDetail,
    DomainList,
    DomainService,
)
from fastapi import APIRouter, Header, Query, Request, Response

router = APIRouter(prefix="/api/m1", tags=["domain"])
ExpectedSession = Annotated[str | None, Header(alias="X-Expected-Session")]
CsrfToken = Annotated[str | None, Header(alias="X-CSRF-Token")]


async def _session(
    request: Request, response: Response, expected: str | None, *, writing: bool = False
) -> SessionView:
    auth, config = access(request, writing=writing)
    session = await auth.session(request.cookies.get(config.cookie_name), expected)
    if expected is None:
        raise AuthError(403, "forbidden", "请先刷新登录状态。")
    response.headers["Cache-Control"] = "no-store"
    return session


@router.get("/domains", response_model=DomainList, responses=ERRORS, operation_id="domain_list")
async def list_domains(
    request: Request, response: Response, expected: ExpectedSession = None
) -> DomainList:
    session = await _session(request, response, expected)
    service: DomainService = request.app.state.domain
    return await service.list_domains(session)


@router.post(
    "/domain-definitions",
    response_model=CreateDomainResponse,
    responses=ERRORS,
    operation_id="domain_save_definition",
)
async def create_domain(
    request: Request,
    response: Response,
    body: CreateDomainRequest,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> CreateDomainResponse:
    session = await _session(request, response, expected, writing=True)
    if csrf is None or not compare_digest(csrf.encode(), session.csrf_token.encode()):
        raise AuthError(403, "forbidden", "请刷新登录状态后重新保存。")
    service: DomainService = request.app.state.domain
    return await service.create_domain(session, body)


@router.get(
    "/domains/{domain_id}/objects/{object_id}",
    response_model=DomainDetail,
    responses=ERRORS,
    operation_id="domain_object_detail",
)
async def domain_detail(
    request: Request,
    response: Response,
    domain_id: UUID,
    object_id: UUID,
    version: Annotated[int | None, Query(ge=1, le=2**63 - 1)] = None,
    expected: ExpectedSession = None,
) -> DomainDetail:
    session = await _session(request, response, expected)
    service: DomainService = request.app.state.domain
    return await service.read_domain(session, domain_id, object_id, version)
