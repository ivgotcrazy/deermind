"""认证HTTP入口：同源检查、Cookie及安全错误；业务会话归Product。"""

import logging
from ipaddress import ip_address
from urllib.parse import urlsplit

from deermind.product.public.auth_config import AuthConfig
from deermind.product.public.authentication import (
    Authentication,
    AuthError,
    SessionView,
    SignInRequest,
    SignInResponse,
    SignOutResponse,
)
from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

LOGGER = logging.getLogger("product.auth")
router = APIRouter(prefix="/api/m1/auth", tags=["authentication"])


class ErrorDetail(BaseModel):
    code: str
    message: str
    issues: list[dict[str, str]]
    retryable: bool


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ErrorDetail


ERRORS: dict[int | str, dict[str, object]] = {
    code: {"model": ErrorResponse} for code in (400, 401, 403, 409, 413, 429, 503)
}
ERRORS["4XX"] = {"model": ErrorResponse}  # 覆盖FastAPI默认422，校验失败统一返回400。


def safe_error(error: AuthError) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if error.retry_after is not None:
        headers["Retry-After"] = str(error.retry_after)
    body = ErrorResponse(
        error=ErrorDetail(
            code=error.code,
            message=error.message,
            issues=[],
            retryable=error.status in {429, 503},
        )
    )
    return JSONResponse(body.model_dump(), status_code=error.status, headers=headers)


async def authentication_error(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, AuthError):
        return safe_error(error)
    if isinstance(error, RequestValidationError):
        # FastAPI默认错误带input，不能将密码或多余的敏感字段反射回去。
        return safe_error(AuthError(400, "invalid_request", "请求格式不正确。"))
    LOGGER.error(
        "认证存储暂不可用",
        exc_info=True,
        extra={
            "action": "authentication",
            "outcome": "failed",
            "error_code": "AUTH_STORAGE_UNAVAILABLE",
        },
    )
    return safe_error(AuthError(503, "temporarily_unavailable", "服务暂不可用，请稍后重试。"))


def access(request: Request, *, writing: bool = False) -> tuple[Authentication, AuthConfig]:
    service: Authentication = request.app.state.auth
    config: AuthConfig = request.app.state.auth_config
    hosts = {urlsplit(origin).netloc for origin in config.origins}
    origin = request.headers.get("origin")
    if (
        request.headers.get("host") not in hosts
        or request.headers.get("sec-fetch-site") == "cross-site"
        or (origin is not None and origin not in config.origins)
        or (writing and origin not in config.origins)
    ):
        raise AuthError(403, "forbidden", "请求来源不允许。")
    return service, config


def source_address(request: Request, config: AuthConfig) -> str:
    if request.client is None:
        raise AuthError(400, "invalid_request", "无法确认请求来源。")
    peer = ip_address(request.client.host)
    # 只信任配置过的反向代理，代理必须覆盖而不是拼接来源头。
    if any(peer in network for network in config.trusted_proxies):
        raw = request.headers.get("x-real-ip")
        if raw is None:
            raise AuthError(400, "invalid_request", "代理没有提供请求来源。")
        try:
            return str(ip_address(raw))
        except ValueError as error:
            raise AuthError(400, "invalid_request", "请求来源格式不正确。") from error
    return str(peer)


def return_path(value: str | None) -> str | None:
    # 当前只有两个正式入口，不接受任意跳转URL或编码绕过。
    if value is not None and value not in {"/admin/", "/student/"}:
        raise AuthError(400, "invalid_request", "返回页面不允许。")
    return value


@router.post(
    "/sign-in", response_model=SignInResponse, responses=ERRORS, operation_id="auth_sign_in"
)
async def sign_in(request: Request, response: Response, body: SignInRequest) -> SignInResponse:
    service, config = access(request, writing=True)
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise AuthError(400, "invalid_request", "登录只接受JSON请求。")
    target = return_path(body.return_to)
    result = await service.sign_in(
        body.login_identifier,
        body.password.get_secret_value(),
        source_address(request, config),
        request.cookies.get(config.cookie_name),
    )
    response.set_cookie(
        config.cookie_name,
        result.token,
        max_age=24 * 60 * 60,
        httponly=True,
        secure=not config.local_http,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return SignInResponse(
        account=result.view.account, expires_at=result.view.expires_at, return_to=target
    )


@router.get("/session", response_model=SessionView, responses=ERRORS, operation_id="auth_session")
async def current_session(request: Request, response: Response) -> SessionView:
    service, config = access(request)
    result = await service.session(request.cookies.get(config.cookie_name))
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/sign-out", response_model=SignOutResponse, responses=ERRORS, operation_id="auth_sign_out"
)
async def sign_out(request: Request, response: Response) -> SignOutResponse:
    service, config = access(request, writing=True)
    await service.sign_out(
        request.cookies.get(config.cookie_name),
        request.headers.get("x-expected-session"),
        request.headers.get("x-csrf-token"),
    )
    response.delete_cookie(
        config.cookie_name, path="/", httponly=True, secure=not config.local_http, samesite="lax"
    )
    response.headers["Cache-Control"] = "no-store"
    return SignOutResponse()
