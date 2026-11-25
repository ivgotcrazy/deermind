"""Check definitions used by a course, independent of the current number of spare questions."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from deermind.foundation.system.public.errors import Issue
from deermind.spaces.domain.instances import chapter_methods, require_definition
from deermind.spaces.domain.public import (
    SolutionDefinition,
    SolutionRef,
    TaskDefinition,
    TaskRef,
    solution_gaps,
    task_gaps,
)


async def check_methods(
    connection: AsyncConnection, domain: UUID, task_ref: TaskRef, methods: list[SolutionRef]
) -> tuple[list[Issue], list[Issue]]:
    knowledge = await chapter_methods(connection, domain, task_ref, methods)
    task = TaskDefinition.model_validate(await require_definition(connection, domain, task_ref))
    detection = task_gaps(task)
    explanation = [*detection]
    for method in methods:
        solution = SolutionDefinition.model_validate(
            await require_definition(connection, domain, method)
        )
        missing = solution_gaps(solution)
        explanation.extend(missing)
        # 缺知识成分只记讲解侧缺口，不计入检测侧阻塞。
        detection.extend(issue for issue in missing if issue.code != "missing_knowledge")
    if not methods:
        # 未采用任何解法，讲解与检测两侧都记缺口。
        issue = Issue(code="missing_methods", path="/methods", message="本章尚未采用解法。")
        explanation.append(issue)
        detection.append(issue)
    for kc in knowledge:
        path = await connection.scalar(
            text(
                "SELECT 1 FROM domain.kc_test_path p "
                "JOIN domain.object_identity t ON p.task_id=t.object_id "
                "JOIN domain.object_version th ON "
                "(th.object_id,th.version)=(t.object_id,t.head_version) "
                "JOIN domain.object_identity s ON p.solution_id=s.object_id "
                "JOIN domain.object_version sh ON "
                "(sh.object_id,sh.version)=(s.object_id,s.head_version) "
                "WHERE p.kc_id=:id AND p.kc_version=:version AND NOT th.is_deleted "
                "AND NOT sh.is_deleted LIMIT 1"
            ),
            {"id": kc.object_id, "version": kc.version},
        )
        if path is None:
            # 该知识成分缺已确认的直接检验路径，记讲解侧缺口。
            explanation.append(
                Issue(
                    code="missing_kc_path",
                    path=f"/kc/{kc.object_id}",
                    message="知识成分尚无已确认的直接检验路径。",
                )
            )
    return explanation, detection
