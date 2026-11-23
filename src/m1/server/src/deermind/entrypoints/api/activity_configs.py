"""活动配置管理入口。"""

from uuid import UUID

from deermind.entrypoints.api.errors import ERRORS
from deermind.entrypoints.api.evaluation import CsrfToken, ExpectedSession, admin_session
from deermind.spaces.interaction.public import (
    ActivityConfigService,
    ActivityType,
    ConfigCommand,
    ConfigReceipt,
    ConfigView,
)
from fastapi import APIRouter, Request, Response

router = APIRouter(prefix="/api/m1/interaction/activity-configs", tags=["interaction"])


@router.get(
    "/{activity_type}",
    response_model=ConfigView,
    responses=ERRORS,
    operation_id="interaction_read_config",
)
async def read_config(
    request: Request,
    response: Response,
    activity_type: ActivityType,
    config_ref: UUID | None = None,
    expected: ExpectedSession = None,
) -> ConfigView:
    await admin_session(request, response, expected)
    service: ActivityConfigService = request.app.state.activity_configs
    return await service.detail(activity_type, config_ref)


@router.put(
    "/{activity_type}",
    response_model=ConfigReceipt,
    responses=ERRORS,
    operation_id="interaction_save_config",
)
async def save_config(
    request: Request,
    response: Response,
    activity_type: ActivityType,
    body: ConfigCommand,
    expected: ExpectedSession = None,
    csrf: CsrfToken = None,
) -> ConfigReceipt:
    session = await admin_session(request, response, expected, csrf, writing=True)
    service: ActivityConfigService = request.app.state.activity_configs
    return await service.save(session.account.account_id, activity_type, body)
