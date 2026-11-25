"""统一API错误外壳及日志；不反射校验输入或数据库异常参数。"""

import logging

from deermind.foundation.system.public.errors import ErrorDetail, ErrorResponse, Issue, RequestError
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
_CONTENT_FIELDS = frozenset(
    """
    schema_version role blocks block_id type provenance transformation note payload source_refs
    source_id owner ref file_id sha256 event_id record_id path file_page printed_page region
    spans text expression op args value name cancel_to lines relation suffix purpose
    data_tables data_id columns key label value_type unit rows row_id cells state data_ref caption
    kind category_column series column color axis min max step legend relationship
    stacked slice_colors
    objects object_id shape relations subject predicate object basis layout view_box boxes box
    points position object_ref meaning constraints task_ref reason applies_to method_refs
    """.split()
)


def safe_error(error: RequestError, *, issues: list[Issue] | None = None) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if error.retry_after is not None:
        # 错误携带重试间隔时，随响应头告知客户端。
        headers["Retry-After"] = str(error.retry_after)
    body = ErrorResponse(
        error=ErrorDetail(
            code=error.code,
            message=error.message,
            issues=error.issues if issues is None else issues,
            retryable=error.status in {429, 503},
        )
    )
    return JSONResponse(
        body.model_dump(exclude_none=True), status_code=error.status, headers=headers
    )


def content_issues(error: RequestValidationError) -> list[Issue]:
    """只公开 RichContent 的约定字段和位置，不回显输入、动态字段或底层异常。"""
    issues: list[Issue] = []
    # 逐条校验错误，仅提取约定字段与位置形成对外 issue。
    for item in error.errors():
        location = item["loc"]
        if len(location) > 1 and location[1] in (
            "domain.create",
            "kc.create",
            "kc.update",
            "task.create",
            "task.update",
            "solution.create",
            "solution.update",
        ):
            # 嵌套命令层位置需剥掉一层，指向实际校验字段。
            location = (location[0], *location[2:])
        if len(location) < 3 or tuple(location[:2]) != ("body", "definition"):
            # 非 definition 文档字段的错误不对外暴露路径。
            continue
        field = location[2]
        if field not in (
            "coverage",
            "description",
            "definition",
            "applicability",
            "examples",
            "non_examples",
            "responsibility",
            "expected_output",
            "completion_conditions",
            "boundaries",
            "approach",
            "rationale",
            "key_process",
            "method_refs",
            "kc_refs",
            "prerequisites",
        ):
            # 不在白名单内的字段名不回显。
            continue
        parts = location[3:]
        if item["type"] == "extra_forbidden":
            # 多余字段错误的末段是被禁字段名，路径回退到其父级。
            parts = parts[:-1]
        segments = [
            str(part)
            for part in parts
            if isinstance(part, int) or (isinstance(part, str) and part in _CONTENT_FIELDS)
        ]
        path = "/".join(["", "definition", field, *segments])
        message = item["msg"] if item["type"] == "invalid_content" else "该处内容不符合结构要求。"
        issues.append(Issue(code="invalid_content", path=path, message=message))
        if len(issues) == 8:
            # 对外 issue 上限 8 条，避免回显过多内部细节。
            break
    return issues


async def api_error(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, RequestError):
        # 业务错误已带对外状态码与文案，直接包装。
        return safe_error(error)
    if isinstance(error, RequestValidationError):
        # 入参校验失败转为 400，issue 仅含白名单字段位置。
        return safe_error(
            RequestError(400, "invalid_request", "请求格式不正确。"),
            issues=content_issues(error),
        )
    if isinstance(error, (RequestConflict, IntegrityError)):
        # 业务冲突或数据库唯一约束冲突，统一映射为 409。
        return safe_error(
            RequestError(409, "request_conflict", "请求身份或内容冲突，请核对后重试。")
        )
    if isinstance(error, HTTPException):
        # Starlette 原生异常按状态码映射对外错误码。
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
    # 数据库类异常按依赖不可用返回 503，其余未预期异常返回 500。
    status = 503 if isinstance(error, SQLAlchemyError) else 500
    code = "temporarily_unavailable" if status == 503 else "internal_error"
    return safe_error(RequestError(status, code, "服务暂不可用，请先查询原请求结果。"))
