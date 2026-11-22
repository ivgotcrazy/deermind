"""管理员领域列表、新建和选中详情的 HTTP 入口。"""

from secrets import compare_digest
from typing import Annotated
from uuid import UUID

from deermind.entrypoints.api.auth import access
from deermind.entrypoints.api.errors import ERRORS
from deermind.product.public.authentication import AuthError, SessionView
from deermind.spaces.domain.public import (
    AnalysisAcceptance,
    AnalysisArtifactView,
    CheckClassification,
    CheckManualInstance,
    ConfirmKCPathRequest,
    ConfirmKCPathResponse,
    CreateDomainResponse,
    DomainAnalysisService,
    DomainInstanceService,
    DomainIntakeActions,
    DomainIntakeQueries,
    DomainList,
    DomainService,
    ExtractDefinition,
    InstanceCommand,
    InstanceList,
    InstanceReceipt,
    InstanceView,
    IntakeAction,
    IntakeActionReceipt,
    IntakeDetail,
    IntakeKind,
    IntakeList,
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


@router.get(
    "/domains/{domain_id}/intake-items",
    response_model=IntakeList,
    responses=ERRORS,
    operation_id="domain_intake_list",
)
async def intake_list(
    request: Request,
    response: Response,
    domain_id: UUID,
    kind: IntakeKind | None = None,
    cursor: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    expected: ExpectedSession = None,
) -> IntakeList:
    session = await _session(request, response, expected)
    if session.account.role != "admin":
        raise AuthError(403, "forbidden", "只有管理员可以查看领域待办。")
    intake: DomainIntakeQueries = request.app.state.domain_intake
    return await intake.list_items(domain_id, kind, cursor, limit, session.account.account_id)


@router.get(
    "/domains/{domain_id}/intake-items/{item_id}",
    response_model=IntakeDetail,
    responses=ERRORS,
    operation_id="domain_intake_detail",
)
async def intake_detail(
    request: Request,
    response: Response,
    domain_id: UUID,
    item_id: UUID,
    expected: ExpectedSession = None,
) -> IntakeDetail:
    session = await _session(request, response, expected)
    if session.account.role != "admin":
        raise AuthError(403, "forbidden", "只有管理员可以查看领域待办。")
    intake: DomainIntakeQueries = request.app.state.domain_intake
    return await intake.detail(domain_id, item_id)


@router.get(
    "/domains/{domain_id}/material-intake-parent",
    response_model=IntakeDetail,
    responses=ERRORS,
    operation_id="domain_intake_material_parent",
)
async def find_material_parent(
    request: Request,
    response: Response,
    domain_id: UUID,
    import_id: UUID,
    candidate_id: UUID,
    revision: Annotated[int, Query(ge=1, le=2**63 - 1)],
    expected: ExpectedSession = None,
) -> IntakeDetail:
    session = await _session(request, response, expected)
    if session.account.role != "admin":
        raise AuthError(403, "forbidden", "只有管理员可以核对入库父题。")
    intake: DomainIntakeQueries = request.app.state.domain_intake
    return await intake.find_material_parent(domain_id, import_id, candidate_id, revision)


@router.post(
    "/domains/{domain_id}/intake-items/{item_id}/actions",
    response_model=IntakeActionReceipt,
    responses=ERRORS,
    operation_id="domain_process_intake",
)
async def process_intake(
    request: Request,
    response: Response,
    domain_id: UUID,
    item_id: UUID,
    body: IntakeAction,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> IntakeActionReceipt:
    session = await _session(request, response, expected, writing=True)
    if (
        session.account.role != "admin"
        or csrf is None
        or not compare_digest(csrf.encode(), session.csrf_token.encode())
    ):
        raise AuthError(403, "forbidden", "请使用有效的管理员会话。")
    processing: DomainIntakeActions = request.app.state.domain_intake_processing
    return await processing.process(domain_id, item_id, session.account.account_id, body)


@router.get(
    "/domains/{domain_id}/intake-items/{item_id}/parent",
    response_model=InstanceView,
    responses=ERRORS,
    operation_id="domain_read_intake_parent",
)
async def read_intake_parent(
    request: Request,
    response: Response,
    domain_id: UUID,
    item_id: UUID,
    expected: ExpectedSession = None,
) -> InstanceView:
    session = await _session(request, response, expected)
    if session.account.role != "admin":
        raise AuthError(403, "forbidden", "只有管理员可以查看待入库父题。")
    processing: DomainIntakeActions = request.app.state.domain_intake_processing
    return await processing.read_parent(domain_id, item_id)


@router.get(
    "/domains/{domain_id}/instances",
    response_model=InstanceList,
    responses=ERRORS,
    operation_id="domain_list_instances",
)
async def list_instances(
    request: Request,
    response: Response,
    domain_id: UUID,
    cursor: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    expected: ExpectedSession = None,
) -> InstanceList:
    session = await _session(request, response, expected)
    if session.account.role != "admin":
        raise AuthError(403, "forbidden", "只有管理员可以查看领域题目。")
    service: DomainInstanceService = request.app.state.domain_instances
    return await service.list_instances(domain_id, cursor, limit)


@router.get(
    "/domains/{domain_id}/instances/{item_id}",
    response_model=InstanceView,
    responses=ERRORS,
    operation_id="domain_read_instance",
)
async def read_instance(
    request: Request,
    response: Response,
    domain_id: UUID,
    item_id: UUID,
    version: Annotated[int | None, Query(ge=1, le=2**63 - 1)] = None,
    expected: ExpectedSession = None,
) -> InstanceView:
    session = await _session(request, response, expected)
    if session.account.role != "admin":
        raise AuthError(403, "forbidden", "只有管理员可以查看领域题目。")
    service: DomainInstanceService = request.app.state.domain_instances
    return await service.read(domain_id, item_id, version)


@router.post(
    "/domains/{domain_id}/instances",
    response_model=InstanceReceipt,
    responses=ERRORS,
    operation_id="domain_save_instance",
)
async def save_instance(
    request: Request,
    response: Response,
    domain_id: UUID,
    body: InstanceCommand,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> InstanceReceipt:
    session = await _session(request, response, expected, writing=True)
    if (
        session.account.role != "admin"
        or csrf is None
        or not compare_digest(csrf.encode(), session.csrf_token.encode())
    ):
        raise AuthError(403, "forbidden", "请使用有效的管理员会话。")
    service: DomainInstanceService = request.app.state.domain_instances
    return await service.save(domain_id, session.account.account_id, body)


async def _analyze(
    request: Request,
    response: Response,
    domain_id: UUID,
    body: ExtractDefinition | CheckClassification | CheckManualInstance,
    expected: str | None,
    csrf: str | None,
) -> AnalysisAcceptance:
    session = await _session(request, response, expected, writing=True)
    if (
        session.account.role != "admin"
        or csrf is None
        or not compare_digest(csrf.encode(), session.csrf_token.encode())
    ):
        raise AuthError(403, "forbidden", "请使用有效的管理员会话。")
    analysis: DomainAnalysisService = request.app.state.domain_analysis
    return await analysis.accept(domain_id, session.account.account_id, body)


@router.post(
    "/domains/{domain_id}/definition-candidates",
    status_code=202,
    response_model=AnalysisAcceptance,
    responses=ERRORS,
    operation_id="domain_extract_definition",
)
async def extract_definition(
    request: Request,
    response: Response,
    domain_id: UUID,
    body: ExtractDefinition,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> AnalysisAcceptance:
    return await _analyze(request, response, domain_id, body, expected, csrf)


@router.post(
    "/domains/{domain_id}/classification-checks",
    status_code=202,
    response_model=AnalysisAcceptance,
    responses=ERRORS,
    operation_id="domain_check_classification",
)
async def check_classification(
    request: Request,
    response: Response,
    domain_id: UUID,
    body: CheckClassification | CheckManualInstance,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> AnalysisAcceptance:
    return await _analyze(request, response, domain_id, body, expected, csrf)


@router.get(
    "/domains/{domain_id}/artifacts/{artifact_id}",
    response_model=AnalysisArtifactView,
    responses=ERRORS,
    operation_id="domain_analysis_artifact",
)
async def read_artifact(
    request: Request,
    response: Response,
    domain_id: UUID,
    artifact_id: UUID,
    expected: ExpectedSession = None,
) -> AnalysisArtifactView:
    session = await _session(request, response, expected)
    if session.account.role != "admin":
        raise AuthError(403, "forbidden", "只有管理员可以查看领域检查产物。")
    analysis: DomainAnalysisService = request.app.state.domain_analysis
    return await analysis.artifact(domain_id, artifact_id)


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
