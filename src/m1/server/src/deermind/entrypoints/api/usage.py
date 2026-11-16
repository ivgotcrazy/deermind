"""学生本人确认入口；管理员线下确认通过管理命令执行。"""

import secrets

from deermind.entrypoints.api.auth import access
from deermind.entrypoints.api.errors import ERRORS
from deermind.product.public.authentication import AuthError
from deermind.product.public.usage import (
    ConfirmUsageRequest,
    ConfirmUsageResponse,
    UsageService,
    UsageView,
)
from fastapi import APIRouter, Request, Response

router = APIRouter(prefix="/api/m1", tags=["usage"])


@router.get(
    "/usage-conditions",
    response_model=UsageView,
    responses=ERRORS,
    operation_id="product_usage_conditions",
)
async def conditions(request: Request, response: Response) -> UsageView:
    auth, config = access(request)
    session = await auth.session(
        request.cookies.get(config.cookie_name), request.headers.get("x-expected-session")
    )
    service: UsageService = request.app.state.usage
    response.headers["Cache-Control"] = "no-store"
    return await service.view(session)


@router.post(
    "/usage-confirmations",
    response_model=ConfirmUsageResponse,
    responses=ERRORS,
    operation_id="product_record_usage_confirmation",
)
async def confirm(
    request: Request, response: Response, body: ConfirmUsageRequest
) -> ConfirmUsageResponse:
    auth, config = access(request, writing=True)
    expected = request.headers.get("x-expected-session")
    csrf = request.headers.get("x-csrf-token")
    session = await auth.session(request.cookies.get(config.cookie_name), expected)
    if (
        expected is None
        or csrf is None
        or not secrets.compare_digest(csrf, session.csrf_token)
        or session.account.role != "student"
    ):
        raise AuthError(403, "forbidden", "请通过本人确认页面提交。")
    service: UsageService = request.app.state.usage
    result = await service.confirm(session, body)
    response.headers["Cache-Control"] = "no-store"
    return result
