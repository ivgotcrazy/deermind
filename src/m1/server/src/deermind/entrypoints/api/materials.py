"""管理员教材登记与原件流的 HTTP 边界。"""

from collections.abc import AsyncIterator
from secrets import compare_digest
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.entrypoints.api.auth import access
from deermind.entrypoints.api.errors import ERRORS
from deermind.foundation.system.files.uploads import FileUploads, UploadView, upload_view
from deermind.foundation.system.public.errors import ErrorResponse, RequestError
from deermind.product.public.authentication import SessionView
from deermind.product.public.chapter_associations import (
    ChapterAssociationCommand,
    ChapterAssociationList,
    ChapterAssociationReceipt,
    ChapterAssociationService,
)
from deermind.product.public.material_assistant import (
    DecideMaterialBatch,
    MaterialAdoptionReceipt,
    MaterialAdoptionService,
    MaterialAssistantService,
    MaterialBatchView,
    MaterialCurrentContents,
    MaterialHistory,
    MaterialMessageInput,
    MaterialTurnAcceptance,
)
from deermind.product.public.material_intake import (
    IntakeAccepted,
    IntakeSubmissionView,
    MaterialIntakeService,
    SubmitDomainIntake,
)
from deermind.product.public.materials import (
    AppendMaterial,
    DeleteMaterial,
    MaterialDeletionReceipt,
    MaterialDeletionService,
    MaterialDetail,
    MaterialDomainRef,
    MaterialReceipt,
    MaterialService,
    NewMaterial,
    RegisterMaterialFile,
    TextbookList,
)
from fastapi import APIRouter, Query, Request, Response
from pydantic import ValidationError
from starlette.background import BackgroundTask
from starlette.requests import ClientDisconnect
from starlette.responses import StreamingResponse

router = APIRouter(prefix="/api/m1", tags=["materials"])
type Cursor = Annotated[str | None, Query(max_length=128)]
type Limit = Annotated[int, Query(ge=1, le=100)]


async def _admin(request: Request, response: Response, *, writing: bool = False) -> SessionView:
    auth, config = access(request, writing=writing)
    expected = request.headers.get("x-expected-session")
    session = await auth.session(request.cookies.get(config.cookie_name), expected)
    if expected is None or session.account.role != "admin":
        # 缺会话标识或非管理员，拒绝访问教材管理入口。
        raise RequestError(403, "forbidden", "请使用管理员会话。")
    if writing and not compare_digest(
        request.headers.get("x-csrf-token", "").encode(), session.csrf_token.encode()
    ):
        # 写操作 CSRF 不符，要求重新登录后提交。
        raise RequestError(403, "forbidden", "请刷新登录状态后重新提交。")
    response.headers["Cache-Control"] = "no-store"
    return session


@router.post(
    "/file-uploads",
    response_model=UploadView,
    responses=ERRORS,
    operation_id="register_file_upload",
)
async def register_upload(
    request: Request, response: Response, body: RegisterMaterialFile
) -> UploadView:
    session = await _admin(request, response, writing=True)
    materials: MaterialService = request.app.state.materials
    await materials.authorize_upload(session, body.domain_ref, body.import_id)
    uploads: FileUploads = request.app.state.uploads
    return await uploads.register(
        session.account.account_id,
        body.request_id,
        body.original_name,
        body.declared_media_type,
        body.declared_byte_size,
        body.domain_ref.model_dump_json(),
        body.import_id,
    )


@router.put(
    "/file-uploads/{upload_id}/content",
    response_model=UploadView,
    responses={**ERRORS, 415: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    operation_id="write_file_upload",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                media: {"schema": {"type": "string", "format": "binary"}}
                for media in ("application/pdf", "image/png", "image/jpeg")
            },
        }
    },
)
async def write_upload(request: Request, response: Response, upload_id: UUID) -> UploadView:
    session = await _admin(request, response, writing=True)
    uploads: FileUploads = request.app.state.uploads
    row = await uploads.read(session.account.account_id, upload_id)
    materials: MaterialService = request.app.state.materials
    identity = UUID(row["resource_ref"]["id"]) if row["resource_ref"] is not None else None
    await materials.authorize_upload(
        session, MaterialDomainRef.model_validate(row["domain_ref"]), identity
    )

    async def chunks() -> AsyncIterator[bytes]:
        try:
            # 按流式分块转发上传内容，空块不写入。
            async for chunk in request.stream():
                if chunk:
                    yield chunk
        except ClientDisconnect as error:
            # 客户端中途断开，本次上传视为来源不可用，需重传。
            raise RequestError(422, "source_unavailable", "上传已中断，请重传此文件。") from error

    return await uploads.write(
        session.account.account_id,
        row,
        request.headers.get("content-type", ""),
        chunks(),
    )


@router.get(
    "/file-uploads/{upload_id}",
    response_model=UploadView,
    responses=ERRORS,
    operation_id="read_file_upload",
)
async def read_upload(request: Request, response: Response, upload_id: UUID) -> UploadView:
    session = await _admin(request, response)
    uploads: FileUploads = request.app.state.uploads
    return upload_view(await uploads.read(session.account.account_id, upload_id))


@router.post(
    "/material-imports",
    response_model=MaterialReceipt,
    responses={**ERRORS, 422: {"model": ErrorResponse}},
    operation_id="create_material_import",
)
async def create_material(
    request: Request, response: Response, body: NewMaterial
) -> MaterialReceipt:
    session = await _admin(request, response, writing=True)
    materials: MaterialService = request.app.state.materials
    return await materials.receive(session, body)


@router.post(
    "/material-imports/{import_id}/files",
    response_model=MaterialReceipt,
    responses={**ERRORS, 422: {"model": ErrorResponse}},
    operation_id="append_material_files",
)
async def append_material(
    request: Request, response: Response, import_id: UUID, body: AppendMaterial
) -> MaterialReceipt:
    session = await _admin(request, response, writing=True)
    materials: MaterialService = request.app.state.materials
    return await materials.receive(session, body, import_id)


@router.get(
    "/textbooks", response_model=TextbookList, responses=ERRORS, operation_id="list_textbooks"
)
async def list_textbooks(
    request: Request,
    response: Response,
    domain_id: UUID | None = None,
    name: Annotated[str, Query(max_length=512)] = "",
    cursor: Cursor = None,
    limit: Limit = 50,
) -> TextbookList:
    session = await _admin(request, response)
    materials: MaterialService = request.app.state.materials
    return await materials.list_books(session, domain_id, name, cursor, limit)


@router.get(
    "/textbooks/{textbook_id}",
    response_model=MaterialDetail,
    responses=ERRORS,
    operation_id="read_textbook",
)
async def read_textbook(
    request: Request,
    response: Response,
    textbook_id: UUID,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> MaterialDetail:
    session = await _admin(request, response)
    materials: MaterialService = request.app.state.materials
    return await materials.detail(session, textbook_id, cursor, limit)


@router.get(
    "/resource-files",
    response_class=StreamingResponse,
    operation_id="read_resource_file",
    responses={
        **ERRORS,
        200: {
            "content": {
                media: {"schema": {"type": "string", "format": "binary"}}
                for media in ("application/pdf", "image/png", "image/jpeg")
            }
        },
    },
)
async def download_resource(
    request: Request,
    response: Response,
    owner_ref: Annotated[str, Query(max_length=512)],
    storage_ref: UUID,
    view: str,
) -> StreamingResponse:
    session = await _admin(request, response)
    try:
        owner = Ref.model_validate_json(owner_ref)
        source_id = UUID(owner.id)
    except (ValidationError, ValueError) as error:
        # 来源引用不是合法 Ref 或 ID，按无效请求处理。
        raise RequestError(400, "invalid_request", "教材来源引用无效。") from error
    if view != "source" or owner.owner != "product" or owner.type != "material_source":
        # 仅放行产品侧教材原件的下载用途，其余按不存在处理。
        raise RequestError(404, "not_found", "找不到此用途的文件。")
    materials: MaterialService = request.app.state.materials
    source, media, size, name = await materials.download(session, source_id, storage_ref)
    return StreamingResponse(
        iter(lambda: source.read(256 * 1024), b""),
        media_type=media,
        headers={
            "Cache-Control": "no-store",
            "Content-Length": str(size),
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name, safe='')}",
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(source.close),
    )


@router.post(
    "/material-imports/{import_id}/messages",
    status_code=202,
    response_model=MaterialTurnAcceptance,
    responses=ERRORS,
    operation_id="material_assistant_send",
)
async def send_material_message(
    request: Request, response: Response, import_id: UUID, body: MaterialMessageInput
) -> MaterialTurnAcceptance:
    session = await _admin(request, response, writing=True)
    assistant: MaterialAssistantService = request.app.state.material_assistant
    return await assistant.accept(session, import_id, body)


@router.get(
    "/material-imports/{import_id}/messages",
    response_model=MaterialHistory,
    responses=ERRORS,
    operation_id="material_assistant_history",
)
async def read_material_history(
    request: Request,
    response: Response,
    import_id: UUID,
    after_seq: Annotated[int, Query(ge=0, le=2**63 - 1)] = 0,
    upper_seq: Annotated[int | None, Query(ge=0, le=2**63 - 1)] = None,
    limit: Limit = 50,
) -> MaterialHistory:
    session = await _admin(request, response)
    assistant: MaterialAssistantService = request.app.state.material_assistant
    return await assistant.history(session, import_id, after_seq, upper_seq, limit)


@router.get(
    "/material-imports/{import_id}/candidate-batches/{batch_id}",
    response_model=MaterialBatchView,
    responses=ERRORS,
    operation_id="material_read_candidate_batch",
)
async def read_material_batch(
    request: Request, response: Response, import_id: UUID, batch_id: UUID
) -> MaterialBatchView:
    session = await _admin(request, response)
    assistant: MaterialAssistantService = request.app.state.material_assistant
    return await assistant.read_batch(session, import_id, batch_id)


@router.post(
    "/material-imports/{import_id}/candidate-batches/{batch_id}/decision",
    response_model=MaterialAdoptionReceipt,
    responses=ERRORS,
    operation_id="material_decide_batch",
)
async def decide_material_batch(
    request: Request, response: Response, import_id: UUID, batch_id: UUID, body: DecideMaterialBatch
) -> MaterialAdoptionReceipt:
    session = await _admin(request, response, writing=True)
    if body.batch_ref.batch_id != batch_id:
        # 路径批次与回执引用不符，拦截跨批次误操作。
        raise RequestError(400, "invalid_reference", "候选批次与请求路径不一致。")
    adoptions: MaterialAdoptionService = request.app.state.material_adoptions
    return await adoptions.decide(session, import_id, body)


@router.get(
    "/material-imports/{import_id}/contents",
    response_model=MaterialCurrentContents,
    responses=ERRORS,
    operation_id="material_current_contents",
)
async def material_current_contents(
    request: Request, response: Response, import_id: UUID, chapter_id: UUID | None = None
) -> MaterialCurrentContents:
    session = await _admin(request, response)
    adoptions: MaterialAdoptionService = request.app.state.material_adoptions
    return await adoptions.contents(session, import_id, chapter_id)


@router.post(
    "/material-imports/{import_id}/intake-submissions",
    status_code=202,
    response_model=IntakeAccepted,
    responses=ERRORS,
    operation_id="submit_domain_intake",
)
async def submit_intake(
    request: Request, response: Response, import_id: UUID, body: SubmitDomainIntake
) -> IntakeAccepted:
    session = await _admin(request, response, writing=True)
    intake: MaterialIntakeService = request.app.state.material_intake
    return await intake.submit(session, import_id, body)


@router.get(
    "/material-imports/{import_id}/intake-submissions/{submission_id}",
    response_model=IntakeSubmissionView,
    responses=ERRORS,
    operation_id="read_material_intake",
)
async def read_intake(
    request: Request, response: Response, import_id: UUID, submission_id: UUID
) -> IntakeSubmissionView:
    session = await _admin(request, response)
    intake: MaterialIntakeService = request.app.state.material_intake
    return await intake.detail(session, import_id, submission_id)


@router.get(
    "/textbooks/{textbook_id}/chapters/{chapter_id}/associations",
    response_model=ChapterAssociationList,
    responses=ERRORS,
    operation_id="chapter_association_list",
)
async def list_associations(
    request: Request,
    response: Response,
    textbook_id: UUID,
    chapter_id: UUID,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> ChapterAssociationList:
    session = await _admin(request, response)
    service: ChapterAssociationService = request.app.state.chapter_associations
    return await service.list(session, textbook_id, chapter_id, cursor, limit)


@router.post(
    "/textbooks/{textbook_id}/chapters/{chapter_id}/associations",
    response_model=ChapterAssociationReceipt,
    responses=ERRORS,
    operation_id="chapter_association_save",
)
async def save_association(
    request: Request,
    response: Response,
    textbook_id: UUID,
    chapter_id: UUID,
    body: ChapterAssociationCommand,
) -> ChapterAssociationReceipt:
    session = await _admin(request, response, writing=True)
    service: ChapterAssociationService = request.app.state.chapter_associations
    return await service.decide(session, textbook_id, chapter_id, body)


@router.post(
    "/material-imports/{import_id}/delete",
    response_model=MaterialDeletionReceipt,
    responses=ERRORS,
    operation_id="delete_material_import",
)
async def delete_material(
    request: Request,
    response: Response,
    import_id: UUID,
    body: DeleteMaterial,
) -> MaterialDeletionReceipt:
    session = await _admin(request, response, writing=True)
    service: MaterialDeletionService = request.app.state.material_deletion
    return await service.delete(session, import_id, body)
