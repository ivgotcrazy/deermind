"""HTTP 与消息共用的安全错误；不得携带原请求、凭据或内部异常。

分层定位：foundation（公共运行底座 / 公开错误合同）
对外契约：Issue/ErrorDetail/ErrorResponse 定义可公开的错误结构；RequestError 供处理方携带状态码与业务码。
边界约束：仅传入可公开文本；原始请求、凭据与内部异常栈不得外泄。
"""

from deermind.abstractions.events import Ref
from pydantic import BaseModel, ConfigDict


class Issue(BaseModel):
    """一条校验/错误明细：错误码、路径、说明与关联引用。"""

    model_config = ConfigDict(extra="forbid")
    code: str
    path: str
    message: str
    related_ref: Ref | None = None


class ErrorDetail(BaseModel):
    """错误详情：错误码、可公开说明、明细列表与是否可重试。"""

    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    issues: list[Issue]
    retryable: bool


class ErrorResponse(BaseModel):
    """对外错误响应体：错误详情与可选请求引用。"""

    model_config = ConfigDict(extra="forbid")
    error: ErrorDetail
    request_ref: str | None = None


class RequestError(Exception):
    """仅传入可公开文本；状态码与业务码由处理方明确指定。"""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        retry_after: int | None = None,
        *,
        issues: list[Issue] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after
        self.issues = issues or []
