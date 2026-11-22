"""公共收据查询入口；身份来自Cookie，结果由已登记所有者授权读取。"""

from typing import Annotated

from deermind.entrypoints.api.auth import access
from deermind.entrypoints.api.errors import ERRORS
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.foundation.system.requests import RequestReceipts
from deermind.product.public.usage import ConfirmationResult
from deermind.spaces.domain.public import SAVE_ACTION, SaveResult
from fastapi import APIRouter, Header, Query, Request, Response

router = APIRouter(prefix="/api/m1", tags=["requests"])
type RequestReceipt = ReceiptView[ConfirmationResult | SaveResult]


@router.get(
    "/requests/receipt",
    response_model=RequestReceipt,
    responses=ERRORS,
    operation_id="runtime_read_request_receipt",
)
async def receipt(
    request: Request,
    response: Response,
    query: Annotated[ReceiptQuery, Query()],
    expected: Annotated[str | None, Header(alias="X-Expected-Session")] = None,
) -> RequestReceipt:
    auth, config = access(request)
    session = await auth.session(request.cookies.get(config.cookie_name), expected)
    if expected is None:
        raise RequestError(403, "forbidden", "请先刷新登录状态。")
    if query.action == SAVE_ACTION and session.account.role != "admin":
        raise RequestError(404, "not_found", "找不到请求。")
    readers: RequestReceipts = request.app.state.receipts
    result = await readers.read(session.account.account_id, session.session_id, query)
    response.headers["Cache-Control"] = "no-store"
    return ReceiptView[ConfirmationResult | SaveResult].model_validate(result.model_dump())
