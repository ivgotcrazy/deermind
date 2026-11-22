"""管理员领域列表、新建和选中详情的 HTTP 入口。"""

from secrets import compare_digest
from typing import Annotated
from uuid import UUID

from deermind.entrypoints.api.auth import access
from deermind.entrypoints.api.errors import ERRORS
from deermind.product.public.authentication import AuthError, SessionView
from deermind.spaces.domain.public import (
    ConfirmKCPathRequest,
    ConfirmKCPathResponse,
    CreateDomainResponse,
    DomainList,
    DomainService,
    MemberKind,
    MemberList,
    ObjectDetail,
    SaveRequest,
    TaskDependencies,
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
    response_model=MemberList,
    responses=ERRORS,
    operation_id="domain_object_list",
)
async def list_objects(
    request: Request,
    response: Response,
    domain_id: UUID,
    kinds: Annotated[list[MemberKind] | None, Query()] = None,
    name: Annotated[str, Query(max_length=512)] = "",
    cursor: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    expected: ExpectedSession = None,
) -> MemberList:
    session = await _session(request, response, expected)
    service: DomainService = request.app.state.domain
    return await service.list_members(session, domain_id, name, cursor, limit, kinds)


@router.get(
    "/domains/{domain_id}/dependencies",
    response_model=TaskDependencies,
    responses=ERRORS,
    operation_id="domain_query_dependencies",
)
async def domain_dependencies(
    request: Request,
    response: Response,
    domain_id: UUID,
    task_id: Annotated[UUID, Query()],
    version: Annotated[int, Query(ge=1, le=2**63 - 1)],
    solution_ids: Annotated[list[UUID] | None, Query()] = None,
    expected: ExpectedSession = None,
) -> TaskDependencies:
    session = await _session(request, response, expected)
    service: DomainService = request.app.state.domain
    return await service.read_dependencies(session, domain_id, task_id, version, solution_ids)


@router.post(
    "/domains/{domain_id}/kc-test-paths",
    response_model=ConfirmKCPathResponse,
    responses=ERRORS,
    operation_id="domain_confirm_kc_path",
)
async def confirm_kc_path(
    request: Request,
    response: Response,
    domain_id: UUID,
    body: ConfirmKCPathRequest,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> ConfirmKCPathResponse:
    session = await _session(request, response, expected, writing=True)
    if csrf is None or not compare_digest(csrf.encode(), session.csrf_token.encode()):
        raise AuthError(403, "forbidden", "请刷新登录状态后重新保存。")
    service: DomainService = request.app.state.domain
    return await service.confirm_kc_path(session, domain_id, body)


@router.get(
    "/domains/{domain_id}/objects/{object_id}",
    response_model=ObjectDetail,
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
) -> ObjectDetail:
    session = await _session(request, response, expected)
    service: DomainService = request.app.state.domain
    return await service.read_object(session, domain_id, object_id, version)
