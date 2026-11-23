"""Prepare a fixed course view; evaluating a course never evaluates a student."""

from collections.abc import Awaitable, Callable, Mapping
from uuid import UUID

from deermind.foundation.system.public.errors import Issue, RequestError
from deermind.product.learning import course_facts as facts
from deermind.product.public.courses import (
    ChapterSnapshot,
    CourseSnapshot,
    EvaluationGap,
    Purpose,
    PurposeCheck,
)
from deermind.product.public.learning_targets import TargetView
from deermind.spaces.domain.public import SolutionRef, TaskRef
from deermind.spaces.interaction.public import ConfigView
from sqlalchemy.ext.asyncio import AsyncConnection

type MethodCheck = Callable[
    [AsyncConnection, UUID, TaskRef, list[SolutionRef]], Awaitable[tuple[list[Issue], list[Issue]]]
]


def issue(code: str, path: str, message: str) -> Issue:
    return Issue(code=code, path=path, message=message)


def _missing() -> Issue:
    return issue("activity_unprepared", "/activity", "尚未配置这类活动。")


async def prepare_course(
    db: AsyncConnection,
    domain: UUID,
    textbook_title: str,
    target: TargetView,
    chapters: list[ChapterSnapshot],
    configs: Mapping[str, ConfigView],
    methods: MethodCheck,
) -> tuple[CourseSnapshot, list[Issue]]:
    checks: list[PurposeCheck] = []
    blockers: list[Issue] = []
    evaluation: list[EvaluationGap] = []
    by_chapter = {chapter.chapter_id: chapter for chapter in chapters}

    for chapter in chapters:
        subject = facts.ref("material_chapter", chapter.chapter_id, chapter.revision)
        reasons = (
            [] if chapter.page_refs else [issue("missing_pages", "/pages", "本章没有可阅读原页。")]
        )
        checks.append(
            PurposeCheck(
                subject_ref=subject,
                purpose="reading",
                status="limited" if reasons else "ready",
                reasons=reasons,
                basis_refs=chapter.page_refs,
            )
        )
        explanation = (
            []
            if chapter.content_refs
            else [issue("missing_content", "/content", "本章缺少已采用的解析内容。")]
        )
        detection: list[Issue] = []
        for entry in chapter.associations:
            try:
                teaching, supply = await methods(db, domain, entry.task_ref, entry.method_refs)
            except RequestError as error:
                if error.code != "invalid_reference":
                    raise
                blockers.append(issue(error.code, f"/chapters/{chapter.chapter_id}", str(error)))
            else:
                explanation.extend(teaching)
                detection.extend(supply)
        if not chapter.associations:
            detection.append(issue("missing_task", "/tasks", "本章尚未采用任务。"))
        purposes: tuple[tuple[Purpose, str, list[Issue]], ...] = (
            ("explanation", "explanation", explanation),
            ("qa", "question_answer", explanation),
            ("practice_feedback", "question_answer", detection),
            ("detection", "detection", detection),
        )
        for purpose, activity, gaps in purposes:
            config = configs.get(activity)
            misses = [*gaps, *(config.gaps if config is not None else [_missing()])]
            reasons = list(
                {(reason.code, reason.path, reason.message): reason for reason in misses}.values()
            )
            checks.append(
                PurposeCheck(
                    subject_ref=subject,
                    purpose=purpose,
                    status="limited" if reasons else "ready",
                    reasons=reasons,
                    basis_refs=[config.config_ref] if config is not None else [],
                )
            )

    for i, item in enumerate(target.items):
        for j, method in enumerate(item.methods):
            for chapter_id in method.chapter_refs:
                chapter = by_chapter.get(chapter_id)
                if chapter is None or not any(
                    entry.association_ref in target.chapter_basis_refs
                    and method.method_ref in entry.method_refs
                    for entry in chapter.associations
                ):
                    blockers.append(
                        issue(
                            "target_outside_course",
                            f"/items/{i}/methods/{j}",
                            "课程选用的章节关联无法承载该目标方法。请重新选择章节或更新目标。",
                        )
                    )
            for k, aspect in enumerate(method.aspects):
                prefix = f"/items/{i}/methods/{j}"
                missing = [
                    entry
                    for entry in target.gaps
                    if entry.path in {prefix, f"{prefix}/aspects/{k}"}
                ]
                if missing:
                    evaluation.append(
                        EvaluationGap(
                            item_id=item.item_id,
                            method_id=method.method_ref.object_id,
                            method_version=method.method_ref.version,
                            aspect_code=aspect.aspect_ref.aspect_code,
                            reasons=[entry.code for entry in missing],
                        )
                    )
        if not set(item.chapter_refs) <= by_chapter.keys():
            blockers.append(issue("target_outside_course", f"/items/{i}", "课程没有包含目标章节。"))
    checks.append(
        PurposeCheck(
            subject_ref=facts.ref(
                "learning_target", target.target_ref.target_id, target.target_ref.revision
            ),
            purpose="evaluation",
            status="blocked" if blockers else "limited" if evaluation else "ready",
            reasons=[*blockers, *target.gaps],
            basis_refs=target.chapter_basis_refs,
        )
    )
    return CourseSnapshot(
        textbook_title=textbook_title,
        target_ref=target.target_ref,
        target_title=target.title,
        chapters=chapters,
        activity_config_refs=[config.config_ref for config in configs.values()],
        readiness=checks,
        items=target.items,
        evaluation_gaps=evaluation,
    ), blockers
