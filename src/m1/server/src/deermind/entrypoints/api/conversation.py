"""学生空间的活动控制、活动目录和正式聊天查询。"""

from typing import Annotated
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.entrypoints.api.courses import Cursor, Page, reader
from deermind.entrypoints.api.errors import ERRORS
from deermind.entrypoints.api.evaluation import CsrfToken, ExpectedSession
from deermind.entrypoints.api.realtime import Command, CommandResult, Realtime, Resource
from deermind.entrypoints.api.realtime_protocol import MESSAGE_BYTES
from deermind.foundation.system.public.errors import RequestError
from deermind.product.public.authentication import SessionView
from deermind.spaces.interaction.public import (
    ActivityCommand,
    ActivityControlReceipt,
    ActivityPage,
    AnswerCommand,
    AnswerReceipt,
    ConversationService,
    CurrentView,
    DetectionRoundService,
    DirectoryView,
    LearningInputAcceptance,
    LearningInputCommand,
    MessagePage,
    OpenDetectionRound,
    PrepareDetectionCommand,
    PresentationCommand,
    PresentationReceipt,
    RetryLearningWork,
    StopReply,
    StudentTurnService,
)
from fastapi import APIRouter, Body, Query, Request, Response
from pydantic import ValidationError

router = APIRouter(prefix="/api/m1/learning-spaces", tags=["interaction"])
SCOPE = "learning_space"


@router.get(
    "/{scope_id}/conversation",
    response_model=CurrentView | ActivityPage | MessagePage,
    responses=ERRORS,
    operation_id="interaction_query_conversation",
)
async def query_conversation(
    request: Request,
    response: Response,
    scope_id: UUID,
    view: DirectoryView,
    activity_ref: UUID | None = None,
    anchor_message_id: UUID | None = None,
    after_seq: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    cursor: Cursor = None,
    limit: Page = 50,
    expected: ExpectedSession = None,
) -> CurrentView | ActivityPage | MessagePage:
    account = await reader(request, response, expected)
    service: ConversationService = request.app.state.conversation
    return await service.read(
        account,
        scope_id,
        view,
        activity=activity_ref,
        anchor=anchor_message_id,
        after=after_seq,
        cursor=cursor,
        limit=limit,
    )


@router.post(
    "/{scope_id}/activity-actions",
    response_model=ActivityControlReceipt,
    responses=ERRORS,
    operation_id="interaction_control_activity",
)
async def control_activity(
    request: Request,
    response: Response,
    scope_id: UUID,
    body: Annotated[ActivityCommand | StopReply | OpenDetectionRound, Body(discriminator="action")],
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> ActivityControlReceipt:
    account = await reader(request, response, expected, csrf, writing=True, student_only=True)
    if isinstance(body, StopReply):
        # 停止当前回复由回合服务处理。
        turns: StudentTurnService = request.app.state.student_turns
        return await turns.stop(account, scope_id, body)
    if isinstance(body, OpenDetectionRound):
        # 开启诊断轮由诊断轮服务处理。
        rounds: DetectionRoundService = request.app.state.detection_rounds
        return await rounds.open(account, scope_id, body)
    service: ConversationService = request.app.state.conversation
    return await service.control(account, scope_id, body)


@router.post(
    "/{scope_id}/presentations",
    response_model=PresentationReceipt,
    responses=ERRORS,
    operation_id="interaction_record_presentation",
)
async def record_presentation(
    request: Request,
    response: Response,
    scope_id: UUID,
    body: PresentationCommand,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> PresentationReceipt:
    account = await reader(request, response, expected, csrf, writing=True, student_only=True)
    service: ConversationService = request.app.state.conversation
    return await service.record_presentation(account, scope_id, body)


@router.post(
    "/{scope_id}/input-retries",
    response_model=LearningInputAcceptance,
    responses=ERRORS,
    status_code=202,
    operation_id="interaction_retry_work",
)
async def retry_input(
    request: Request,
    response: Response,
    scope_id: UUID,
    body: RetryLearningWork,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> LearningInputAcceptance:
    account = await reader(request, response, expected, csrf, writing=True, student_only=True)
    turns: StudentTurnService = request.app.state.student_turns
    return await turns.retry(account, scope_id, body)


@router.post(
    "/{scope_id}/inputs",
    response_model=LearningInputAcceptance,
    responses=ERRORS,
    operation_id="interaction_handle_input",
    status_code=202,
)
async def handle_input(
    request: Request,
    response: Response,
    scope_id: UUID,
    body: LearningInputCommand,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> LearningInputAcceptance:
    account = await reader(request, response, expected, csrf, writing=True, student_only=True)
    command = Command(
        type="command",
        frame_id=body.request_id,
        request_id=body.request_id,
        action="learning.input",
        resource=Resource(kind=SCOPE, id=str(scope_id)),
        payload=body.model_dump(mode="json", exclude={"request_id"}),
    )
    if command.business_size() > MESSAGE_BYTES:
        # 业务载荷超出实时通道单帧上限，拒绝提交。
        raise RequestError(413, "payload_too_large", "输入超过聊天大小限制。")
    turns: StudentTurnService = request.app.state.student_turns
    return await turns.accept(account, scope_id, body)


def connect_realtime(hub: Realtime, turns: StudentTurnService) -> None:
    """只接入已有业务命令和同一空间的读取权限。"""

    async def authorized(session: SessionView, resource: Resource, _views: frozenset[str]) -> bool:
        if resource.kind != SCOPE or session.account.usage_gaps:
            # 资源类型不符，或账号存在未通过的使用缺口，拒绝订阅。
            return False
        try:
            await turns.check_space(session.account, UUID(resource.id))
        except (RequestError, ValueError):
            # 无空间访问权限或资源 ID 非法，按未授权处理。
            return False
        return True

    async def receive(session: SessionView, frame: Command) -> CommandResult:
        if session.account.role != "student":
            # 实时消息通道仅向学生开放。
            raise RequestError(403, "forbidden", "仅学生可以发送学习消息。")
        try:
            command = LearningInputCommand.model_validate_json(
                canonical_json({"request_id": frame.request_id, **frame.payload})
            )
        except ValidationError as error:
            # 帧载荷不符合学习消息合同，按无效请求返回。
            raise RequestError(400, "invalid_request", "请输入有效的学习消息。") from error
        got = await turns.accept(session.account, UUID(frame.resource.id), command)
        return CommandResult(
            state="accepted",
            owner_receipt_ref=str(got.request_ref),
            execution_ref=str(got.execution_ref),
        )

    hub.authorize = authorized
    hub.commands["learning.input"] = receive


@router.post(
    "/{scope_id}/answers",
    response_model=AnswerReceipt,
    responses=ERRORS,
    operation_id="interaction_submit_answer",
)
async def submit_answer(
    request: Request,
    response: Response,
    scope_id: UUID,
    body: AnswerCommand,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> AnswerReceipt:
    account = await reader(request, response, expected, csrf, writing=True, student_only=True)
    turns: StudentTurnService = request.app.state.student_turns
    return await turns.submit_answer(account, scope_id, body)


@router.post(
    "/{scope_id}/detection-plans",
    response_model=LearningInputAcceptance,
    responses=ERRORS,
    status_code=202,
    operation_id="interaction_prepare_detection",
)
async def prepare_detection(
    request: Request,
    response: Response,
    scope_id: UUID,
    body: PrepareDetectionCommand,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> LearningInputAcceptance:
    account = await reader(request, response, expected, csrf, writing=True, student_only=True)
    turns: StudentTurnService = request.app.state.student_turns
    return await turns.prepare_detection(account, scope_id, body)
