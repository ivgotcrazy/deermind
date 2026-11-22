"""管理员领域列表、新建和选中详情的 HTTP 入口。"""

from secrets import compare_digest
from typing import Annotated, Literal
from uuid import UUID

from deermind.entrypoints.api.auth import access
from deermind.entrypoints.api.errors import ERRORS
from deermind.product.public.authentication import AuthError, SessionView
from deermind.spaces.domain.public import (
    CreateDomainResponse,
    DomainDetail,
    DomainList,
    DomainService,
    KnowledgeDetail,
    KnowledgeList,
    SaveRequest,
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
async def save_definition(
    request: Request,
    response: Response,
    body: SaveRequest,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> CreateDomainResponse:
    session = await _session(request, response, expected, writing=True)
    if csrf is None or not compare_digest(csrf.encode(), session.csrf_token.encode()):
        raise AuthError(403, "forbidden", "请刷新登录状态后重新保存。")
    service: DomainService = request.app.state.domain
    return await service.save_definition(session, body)


@router.get(
    "/domains/{domain_id}/objects",
    response_model=KnowledgeList,
    responses=ERRORS,
    operation_id="domain_object_list",
)
async def list_objects(
    request: Request,
    response: Response,
    domain_id: UUID,
    kinds: Annotated[list[Literal["kc"]] | None, Query()] = None,
    name: Annotated[str, Query(max_length=512)] = "",
    cursor: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    expected: ExpectedSession = None,
) -> KnowledgeList:
    session = await _session(request, response, expected)
    service: DomainService = request.app.state.domain
    return await service.list_knowledge(session, domain_id, name, cursor, limit)


@router.get(
    "/domains/{domain_id}/objects/{object_id}",
    response_model=DomainDetail | KnowledgeDetail,
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
) -> DomainDetail | KnowledgeDetail:
    session = await _session(request, response, expected)
    service: DomainService = request.app.state.domain
    return await service.read_object(session, domain_id, object_id, version)
