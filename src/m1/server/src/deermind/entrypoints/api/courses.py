"""Course adoption and scoped space queries."""

from secrets import compare_digest
from typing import Annotated
from uuid import UUID

from deermind.entrypoints.api.auth import access
from deermind.entrypoints.api.errors import ERRORS
from deermind.entrypoints.api.evaluation import CsrfToken, ExpectedSession, admin_session
from deermind.foundation.system.public.errors import RequestError
from deermind.product.public.authentication import AccountView
from deermind.product.public.courses import (
    AdoptionView,
    ApplicationHead,
    CourseApplyReceipt,
    CourseApplyService,
    CourseCheckCommand,
    CourseCheckReceipt,
    CourseCheckService,
    CourseConfirmCommand,
    CourseOptions,
    LearningSpaceService,
    SpaceChapterContent,
    SpaceCommand,
    SpaceGoalView,
    SpaceList,
    SpaceReceipt,
)
from fastapi import APIRouter, Query, Request, Response
from pydantic import JsonValue

router = APIRouter(prefix="/api/m1", tags=["courses-and-spaces"])
Page = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(max_length=128)]


async def reader(
    request: Request,
    response: Response,
    expected: str | None,
    csrf: str | None = None,
    *,
    writing: bool = False,
    student_only: bool = False,
) -> AccountView:
    auth, settings = access(request, writing=writing)
    session = await auth.session(request.cookies.get(settings.cookie_name), expected)
    if expected is None or (
        writing and (csrf is None or not compare_digest(csrf.encode(), session.csrf_token.encode()))
    ):
        raise RequestError(403, "forbidden", "请刷新登录后再试。")
    account = session.account
    if student_only and account.role != "student":
        raise RequestError(403, "forbidden", "请使用学生账号。")
    if account.role == "student" and account.usage_gaps:
        raise RequestError(403, "usage_not_ready", "请先完成使用确认。")
    response.headers["Cache-Control"] = "no-store"
    return account


@router.get(
    "/course-applications/current",
    response_model=ApplicationHead,
    responses=ERRORS,
    operation_id="product_course_head",
)
async def current_course(
    request: Request,
    response: Response,
    textbook_id: UUID,
    target_id: UUID,
    expected: ExpectedSession = None,
) -> ApplicationHead:
    await admin_session(request, response, expected)
    checks: CourseCheckService = request.app.state.course_checks
    return await checks.head(textbook_id, target_id)


@router.post(
    "/course-applications/checks",
    response_model=CourseCheckReceipt,
    responses=ERRORS,
    operation_id="product_check_course",
)
async def check_course(
    request: Request,
    response: Response,
    body: CourseCheckCommand,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> CourseCheckReceipt:
    session = await admin_session(request, response, expected, csrf, writing=True)
    service: CourseCheckService = request.app.state.course_checks
    return await service.check(session.account.account_id, body)


@router.post(
    "/course-applications/confirmations",
    response_model=CourseApplyReceipt,
    responses=ERRORS,
    operation_id="product_confirm_course",
)
async def confirm_course(
    request: Request,
    response: Response,
    body: CourseConfirmCommand,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> CourseApplyReceipt:
    session = await admin_session(request, response, expected, csrf, writing=True)
    service: CourseApplyService = request.app.state.course_applications
    return await service.confirm(session.account.account_id, body)


@router.get(
    "/course-options",
    response_model=CourseOptions,
    responses=ERRORS,
    operation_id="product_courses",
)
async def course_options(
    request: Request,
    response: Response,
    domain_id: UUID | None = None,
    cursor: Cursor = None,
    limit: Page = 50,
    expected: ExpectedSession = None,
) -> CourseOptions:
    account = await reader(request, response, expected, student_only=True)
    service: LearningSpaceService = request.app.state.course_spaces
    return await service.options(account, domain_id, cursor, limit)


@router.post(
    "/learning-spaces/open",
    response_model=SpaceReceipt,
    responses=ERRORS,
    operation_id="product_open_space",
)
async def open_space(
    request: Request,
    response: Response,
    body: SpaceCommand,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> SpaceReceipt:
    account = await reader(request, response, expected, csrf, writing=True, student_only=True)
    service: LearningSpaceService = request.app.state.course_spaces
    return await service.open(account, body)


@router.get(
    "/learning-spaces",
    response_model=SpaceList,
    responses=ERRORS,
    operation_id="product_list_spaces",
)
async def list_spaces(
    request: Request,
    response: Response,
    student_id: UUID | None = None,
    textbook_id: UUID | None = None,
    target_id: UUID | None = None,
    student_name: Annotated[str, Query(max_length=160)] = "",
    cursor: Cursor = None,
    limit: Page = 50,
    expected: ExpectedSession = None,
) -> SpaceList:
    account = await reader(request, response, expected)
    service: LearningSpaceService = request.app.state.course_spaces
    return await service.list_spaces(
        account, student_id, textbook_id, target_id, student_name.strip(), cursor, limit
    )


@router.get(
    "/learning-spaces/{space_id}",
    response_model=AdoptionView,
    responses=ERRORS,
    operation_id="product_space_adoption",
)
async def space_adoption(
    request: Request,
    response: Response,
    space_id: UUID,
    expected: ExpectedSession = None,
) -> AdoptionView:
    account = await reader(request, response, expected)
    service: LearningSpaceService = request.app.state.course_spaces
    return await service.current_adoption(account, space_id)


@router.get(
    "/learning-spaces/{space_id}/goal",
    response_model=SpaceGoalView,
    responses=ERRORS,
    operation_id="product_space_goal",
)
async def space_goal(
    request: Request,
    response: Response,
    space_id: UUID,
    expected: ExpectedSession = None,
) -> SpaceGoalView:
    account = await reader(request, response, expected)
    service: LearningSpaceService = request.app.state.course_spaces
    return await service.current_goal(account, space_id)


@router.get(
    "/learning-spaces/{space_id}/chapters/{chapter_id}",
    response_model=SpaceChapterContent,
    responses=ERRORS,
    operation_id="product_space_chapter",
)
async def space_chapter(
    request: Request,
    response: Response,
    space_id: UUID,
    chapter_id: UUID,
    expected: ExpectedSession = None,
) -> SpaceChapterContent:
    account = await reader(request, response, expected)
    service: LearningSpaceService = request.app.state.course_spaces
    return SpaceChapterContent(items=await service.chapter_content(account, space_id, chapter_id))


@router.get(
    "/learning-spaces/{space_id}/events",
    response_model=dict[str, JsonValue],
    responses=ERRORS,
    operation_id="product_space_events",
)
async def space_events(
    request: Request,
    response: Response,
    space_id: UUID,
    event_type: Annotated[list[str] | None, Query(max_length=10)] = None,
    after_seq: Annotated[int, Query(ge=0)] = 0,
    upper_seq: Annotated[int | None, Query(ge=0)] = None,
    limit: Page = 50,
    expected: ExpectedSession = None,
) -> dict[str, JsonValue]:
    await admin_session(request, response, expected)
    service: LearningSpaceService = request.app.state.course_spaces
    return await service.list_events(space_id, tuple(event_type or []), after_seq, upper_seq, limit)
