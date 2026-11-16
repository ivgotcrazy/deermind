"""认证HTTP入口：同源检查、Cookie及安全错误；业务会话归Product。"""

from ipaddress import ip_address
from urllib.parse import urlsplit

from deermind.entrypoints.api.errors import ERRORS
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

router = APIRouter(prefix="/api/m1/auth", tags=["authentication"])


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
