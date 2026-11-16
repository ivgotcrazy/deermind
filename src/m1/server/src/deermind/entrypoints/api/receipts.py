"""公共收据查询入口；身份来自Cookie，结果由已登记所有者授权读取。"""

from typing import Annotated

from deermind.entrypoints.api.auth import access
from deermind.entrypoints.api.errors import ERRORS
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.foundation.system.requests import RequestReceipts
from deermind.product.public.usage import ConfirmationResult
from fastapi import APIRouter, Header, Query, Request, Response

router = APIRouter(prefix="/api/m1", tags=["requests"])


@router.get(
    "/requests/receipt",
    response_model=ReceiptView[ConfirmationResult],
    responses=ERRORS,
    operation_id="runtime_read_request_receipt",
)
async def receipt(
    request: Request,
    response: Response,
    query: Annotated[ReceiptQuery, Query()],
    expected: Annotated[str | None, Header(alias="X-Expected-Session")] = None,
) -> ReceiptView[ConfirmationResult]:
    auth, config = access(request)
    session = await auth.session(request.cookies.get(config.cookie_name), expected)
    if expected is None:
        raise RequestError(403, "forbidden", "请先刷新登录状态。")
    readers: RequestReceipts = request.app.state.receipts
    result = await readers.read(session.account.account_id, session.session_id, query)
    response.headers["Cache-Control"] = "no-store"
    return ReceiptView[ConfirmationResult].model_validate(result)
