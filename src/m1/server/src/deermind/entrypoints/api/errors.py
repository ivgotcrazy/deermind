"""统一API错误外壳及日志；不反射校验输入或数据库异常参数。"""

import logging

from deermind.foundation.system.public.errors import ErrorDetail, ErrorResponse, RequestError
from deermind.product.public.errors import RequestConflict
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException

LOGGER = logging.getLogger("runtime.http")
ERRORS: dict[int | str, dict[str, object]] = {
    code: {"model": ErrorResponse} for code in (400, 401, 403, 404, 405, 409, 413, 429, 500, 503)
}
ERRORS["4XX"] = {"model": ErrorResponse}


def safe_error(error: RequestError) -> JSONResponse:
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
    return JSONResponse(
        body.model_dump(exclude_none=True), status_code=error.status, headers=headers
    )


async def api_error(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, RequestError):
        return safe_error(error)
    if isinstance(error, RequestValidationError):
        return safe_error(RequestError(400, "invalid_request", "请求格式不正确。"))
    if isinstance(error, (RequestConflict, IntegrityError)):
        return safe_error(
            RequestError(409, "request_conflict", "请求身份或内容冲突，请核对后重试。")
        )
    if isinstance(error, HTTPException):
        code = {404: "not_found", 405: "method_not_allowed", 503: "temporarily_unavailable"}.get(
            error.status_code, "invalid_request"
        )
        return safe_error(RequestError(error.status_code, code, "请求无法处理。"))
    # 不记录异常正文及SQL参数；类别、操作和追踪栈位置足以定位这层错误。
    LOGGER.error(
        "API处理失败，未返回业务结果",
        exc_info=(type(error), error, error.__traceback__),
        extra={"action": "api_request", "outcome": "failed", "error_code": type(error).__name__},
    )
    status = 503 if isinstance(error, SQLAlchemyError) else 500
    code = "temporarily_unavailable" if status == 503 else "internal_error"
    return safe_error(RequestError(status, code, "服务暂不可用，请先查询原请求结果。"))
