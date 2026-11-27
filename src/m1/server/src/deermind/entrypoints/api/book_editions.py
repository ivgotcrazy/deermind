"""Book edition endpoints for the editor and the student's fixed course."""

from uuid import UUID

from deermind.entrypoints.api.courses import reader
from deermind.entrypoints.api.errors import ERRORS
from deermind.entrypoints.api.materials import material_admin
from deermind.foundation.system.public.errors import RequestError
from deermind.product.public.material_editions import (
    BookPage,
    Edition,
    EditionCommand,
    EditionInfo,
    EditionUsage,
    MapTask,
    StudentBook,
)
from fastapi import APIRouter, Request, Response

router = APIRouter(prefix="/api/m1", tags=["book-editions"], responses=ERRORS)
BOOK = "/textbooks/{book}/editions"
SPACE = "/learning-spaces/{space_id}/book"


@router.get(BOOK, operation_id="list_material_editions")
async def listing(request: Request, response: Response, book: UUID) -> list[EditionInfo]:
    await material_admin(request, response)
    return await request.app.state.material_editions.listing(book)


@router.get(BOOK + "/pages", operation_id="material_edition_pages")
async def pages(request: Request, response: Response, book: UUID) -> list[BookPage]:
    await material_admin(request, response)
    return await request.app.state.material_editions.pages(book)


@router.get(BOOK + "/catalog", operation_id="material_task_catalog")
async def catalog(request: Request, response: Response, book: UUID) -> list[MapTask]:
    session = await material_admin(request, response)
    materials = request.app.state.materials
    detail = await materials.detail(session, book, None, 1)
    return await request.app.state.material_editions.catalog(
        session, detail.material.textbook.domain_id
    )


@router.get(BOOK + "/pages/{page_id}", operation_id="material_page_image", response_class=Response)
async def image(request: Request, response: Response, book: UUID, page_id: UUID) -> Response:
    await material_admin(request, response)
    service = request.app.state.material_editions
    return await page_image(request, await service.pages(book), page_id)


@router.get(BOOK + "/{edition}", operation_id="read_material_edition")
async def detail(
    request: Request, response: Response, book: UUID, edition: UUID, page_id: UUID | None = None
) -> Edition:
    await material_admin(request, response)
    return await request.app.state.material_editions.detail(book, edition, page_id)


@router.get(BOOK + "/{edition}/usage", operation_id="material_edition_usage")
async def usage(
    request: Request, response: Response, book: UUID, edition: UUID
) -> list[EditionUsage]:
    await material_admin(request, response)
    return await request.app.state.material_editions.usage(book, edition)


@router.post(BOOK + "/{edition}", operation_id="edit_material_edition")
async def edit(
    request: Request, response: Response, book: UUID, edition: UUID, body: EditionCommand
) -> EditionInfo:
    session = await material_admin(request, response, writing=True)
    return await request.app.state.material_editions.command(session, book, edition, body)


@router.get(SPACE, operation_id="student_book_edition")
async def student_book(request: Request, response: Response, space_id: UUID) -> StudentBook:
    account = await reader(
        request, response, request.headers.get("x-expected-session"), student_only=True
    )
    work = await request.app.state.course_spaces.workspace(account, space_id)
    value = await request.app.state.material_editions.for_target(
        work.space.textbook_id, work.space.target_id, work.space.target_revision
    )
    if value is None:
        raise RequestError(404, "not_found", "该学习空间采用的课程版本没有已发布的内容树。")
    return value


async def page_image(request: Request, pages: list[BookPage], page_id: UUID) -> Response:
    page = next((p for p in pages if p.page_id == page_id), None)
    if page is None:
        raise RequestError(404, "not_found", "该页不属于选定教材。")
    data = await request.app.state.render_book_page(page)
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


@router.get(
    SPACE + "/pages/{page_id}", operation_id="student_book_page_image", response_class=Response
)
async def student_page(
    request: Request, response: Response, space_id: UUID, page_id: UUID
) -> Response:
    fixed = await student_book(request, response, space_id)
    return await page_image(request, fixed.tree.pages, page_id)
