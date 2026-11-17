"""HTTP与消息共用的安全错误；不得携带原请求、凭据或内部异常。"""

from deermind.abstractions.events import Ref
from pydantic import BaseModel, ConfigDict


class Issue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    path: str
    message: str
    related_ref: Ref | None = None


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    issues: list[Issue]
    retryable: bool


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ErrorDetail
    request_ref: str | None = None


class RequestError(Exception):
    """仅传入可公开文本；状态码与业务码由处理方明确指定。"""

    def __init__(
        self, status: int, code: str, message: str, retry_after: int | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after
