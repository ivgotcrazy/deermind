"""登录HTTP及内部身份合同；凭据不能进入业务收据、事件或普通日志。"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class AuthModel(BaseModel):
    """认证入口拒绝未声明字段，不从客户端接受角色或权限。"""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class SignInRequest(AuthModel):
    """长度及限额由已确认的部署配置校验；不截断密码。"""

    login_identifier: str = Field(min_length=1, max_length=256)
    password: SecretStr = Field(min_length=15, max_length=128)
    return_to: str | None = None


class UsageGap(AuthModel):
    """未满足的使用条件；本轮不推定监护和使用确认已完成。"""

    code: str
    path: str
    message: str


class AccountView(AuthModel):
    account_id: UUID
    display_name: str
    role: Literal["student", "admin"]
    usage_gaps: list[UsageGap]


class SignInResponse(AuthModel):
    account: AccountView
    expires_at: datetime
    return_to: str | None


class SessionView(AuthModel):
    """session_id是诊断身份；浏览器登录秘密只通过HttpOnly Cookie传递。"""

    account: AccountView
    session_id: UUID
    csrf_token: str
    expires_at: datetime


class SignOutResponse(AuthModel):
    signed_out: Literal[True] = True


class AuthError(Exception):
    """可展示的认证错误；不携带密码、数据库参数或原始异常。"""

    def __init__(
        self, status: int, code: str, message: str, retry_after: int | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


@dataclass(frozen=True)
class LoginResult:
    view: SessionView
    token: str = field(repr=False)


class Authentication(Protocol):
    """入口经端口使用认证，不直接读取Product表。"""

    async def sign_in(
        self, login: str, password: str, source: str, old_token: str | None
    ) -> LoginResult: ...
    async def session(self, token: str | None, expected: str | None = None) -> SessionView: ...
    async def sign_out(self, token: str | None, expected: str | None, csrf: str | None) -> None: ...
