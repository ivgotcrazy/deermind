"""Register only the supplemental reads owned by the learning reply."""

from deermind.abstractions.ai.contracts import CallHandle
from deermind.abstractions.ai.tools import ToolResult
from deermind.foundation.ai.execution import Calls
from deermind.foundation.ai.tools import Tool, Tools
from deermind.foundation.system.public.errors import RequestError
from deermind.spaces.interaction.learning_materials import (
    TOOL_REFS,
    ReadCourse,
    ReadKind,
    ReadMaterial,
    ReadPage,
    ReadSection,
    course_result,
    read_activity,
    read_scope,
    result,
    selected_reference,
    unavailable,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


def configure_student_tools(
    engine: AsyncEngine, read_course: ReadCourse | None, calls: Calls
) -> Tools:
    def register(kind: ReadKind, description: str, parameters: type[ReadMaterial]) -> Tool:
        async def check(db: AsyncConnection, handle: CallHandle, args: BaseModel) -> bool:
            return isinstance(args, ReadMaterial) and await read_scope(db, handle) is not None

        async def invoke(handle: CallHandle, args: BaseModel, _work_key: str | None) -> ToolResult:
            assert isinstance(args, ReadMaterial)
            reference = selected_reference(handle, kind, args.number)
            if reference is None:
                return unavailable()
            try:
                async with engine.connect() as db:
                    await calls.guard(db, handle)
                    selected = await read_scope(db, handle)
                    if selected is None:
                        return unavailable()
                    scope, adoption = selected
                    if kind == "activity":
                        before = args.before if isinstance(args, ReadPage) else None
                        content = await read_activity(db, scope, reference, before)
                    else:
                        read = (
                            await read_course(db, scope, adoption, reference)
                            if read_course
                            else None
                        )
                        if read is None:
                            content = unavailable()
                        elif isinstance(args, ReadSection):
                            content = course_result(read[0], read[1], args.section)
                        else:
                            content = result({"material": read[0]}, read[1])
                    await calls.guard(db, handle)
                    return content if await read_scope(db, handle) == selected else unavailable()
            except RequestError as error:
                if error.status == 413:
                    return result({"omission": "材料过长，请学生指出具体段落。"}, [reference])
                if error.status == 404:
                    return unavailable()
                raise

        return Tool(
            TOOL_REFS[kind],
            TOOL_REFS[kind].id,
            description,
            parameters,
            "read",
            4,
            check,
            invoke,
        )

    return Tools(
        calls,
        [
            register(
                "activity",
                "补读活动原文、已呈现题面或已提供的帮助。向前翻页使用返回的 before。",
                ReadPage,
            ),
            register(
                "course",
                "补读已采用的教材段落、任务、题目或解法。按返回的 section 选段。",
                ReadSection,
            ),
            register("published", "补读固定任务的掌握状态或目标判断。", ReadMaterial),
        ],
    )
