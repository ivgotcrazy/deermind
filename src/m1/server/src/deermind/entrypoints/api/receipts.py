"""公共收据查询入口；身份来自Cookie，结果由已登记所有者授权读取。"""

from typing import Annotated

from deermind.entrypoints.api.auth import access
from deermind.entrypoints.api.errors import ERRORS
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.foundation.system.requests import RequestReceipts
from deermind.product.public.chapter_associations import CHAPTER_ACTION, ChapterAssociationResult
from deermind.product.public.courses import (
    CHECK_COURSE,
    CONFIRM_COURSE,
    CourseApplyResult,
    CourseCheckResult,
    SpaceOpenResult,
)
from deermind.product.public.learning_targets import SAVE_TARGET, TargetDetail
from deermind.product.public.material_assistant import (
    CONVERSE,
    DECIDE,
    AdoptedMaterialResult,
    MaterialTurnResult,
)
from deermind.product.public.material_intake import SUBMIT_INTAKE, IntakeSubmissionView
from deermind.product.public.materials import (
    DELETE_MATERIAL,
    RECEIVE_MATERIAL,
    MaterialDeletionResult,
    MaterialResult,
)
from deermind.product.public.usage import ConfirmationResult
from deermind.spaces.domain.public import (
    CLASSIFY,
    CONFIRM_PATH_ACTION,
    EXTRACT,
    PROCESS_INTAKE,
    SAVE_ACTION,
    SAVE_INSTANCE,
    AnalysisReceipt,
    ConfirmKCPathResult,
    InstanceView,
    IntakeActionResult,
    SaveResult,
)
from deermind.spaces.evaluation.public import MANAGE_CLAIM, ClaimResult
from deermind.spaces.interaction.public import (
    MANAGE_ACTIVITY,
    ActivityControlResult,
    ConfigResult,
    LearningTurnResult,
)
from fastapi import APIRouter, Header, Query, Request, Response
from pydantic import TypeAdapter

router = APIRouter(prefix="/api/m1", tags=["requests"])
type RequestReceipt = ReceiptView[
    ConfirmationResult
    | SaveResult
    | ConfirmKCPathResult
    | MaterialResult
    | MaterialTurnResult
    | AdoptedMaterialResult
    | IntakeSubmissionView
    | AnalysisReceipt
    | IntakeActionResult
    | InstanceView
    | ChapterAssociationResult
    | MaterialDeletionResult
    | ClaimResult
    | ConfigResult
    | TargetDetail
    | CourseCheckResult
    | CourseApplyResult
    | SpaceOpenResult
    | ActivityControlResult
    | LearningTurnResult
]
_RECEIPT = TypeAdapter(RequestReceipt)


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
    if (
        query.action
        in (
            SAVE_ACTION,
            CONFIRM_PATH_ACTION,
            RECEIVE_MATERIAL,
            CONVERSE,
            DECIDE,
            SUBMIT_INTAKE,
            EXTRACT,
            CLASSIFY,
            PROCESS_INTAKE,
            SAVE_INSTANCE,
            DELETE_MATERIAL,
            CHAPTER_ACTION,
            MANAGE_CLAIM,
            MANAGE_ACTIVITY,
            SAVE_TARGET,
            CHECK_COURSE,
            CONFIRM_COURSE,
        )
        and session.account.role != "admin"
    ):
        raise RequestError(404, "not_found", "找不到请求。")
    readers: RequestReceipts = request.app.state.receipts
    result = await readers.read(session.account.account_id, session.session_id, query)
    response.headers["Cache-Control"] = "no-store"
    return _RECEIPT.validate_python(result.model_dump())
