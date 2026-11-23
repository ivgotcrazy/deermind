"""Compose the public course and Evaluation dependencies for API and Worker."""

from uuid import UUID

from deermind.bootstrap.settings import Settings
from deermind.bootstrap.student_operation import student_config
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.product.learning.course_applications import CourseApplications
from deermind.product.learning.course_checks import CourseChecks
from deermind.product.learning.course_spaces import CourseSpaces
from deermind.product.learning.targets import TargetDefinitions
from deermind.product.persistence import receipts
from deermind.product.public.authentication import AccountView
from deermind.product.public.courses import AdoptionView, CourseSnapshot
from deermind.spaces.domain.course_readiness import check_methods
from deermind.spaces.domain.supply import TaskSupply
from deermind.spaces.evaluation.goal_results import GoalResults
from deermind.spaces.interaction.configurations import ActivityConfigs
from deermind.spaces.interaction.conversation import Conversation
from deermind.spaces.interaction.conversation_facts import ACCEPTED, COMPLETED
from deermind.spaces.interaction.public import ActivityType, ConfigView
from deermind.spaces.interaction.rounds import DetectionRounds
from deermind.spaces.interaction.student_turns import StudentTurns
from sqlalchemy.ext.asyncio import AsyncConnection

STUDENT_VIEWS = {
    (event_type, "learning_space"): frozenset({"conversation", "activity_tree"})
    for event_type in (ACCEPTED, COMPLETED)
}


def configure_rounds(turns: StudentTurns) -> DetectionRounds:
    return DetectionRounds(turns, TaskSupply.read_fixed_question)


def configure_courses(
    targets: TargetDefinitions, configs: ActivityConfigs
) -> tuple[CourseChecks, CourseSpaces, CourseApplications]:
    checks = CourseChecks(targets, configs.fixed_config, check_methods)
    spaces = CourseSpaces(checks, GoalResults.current)
    return checks, spaces, CourseApplications(checks, spaces)


def configure_goals(targets: TargetDefinitions, configs: ActivityConfigs) -> GoalResults:
    _checks, spaces, _applications = configure_courses(targets, configs)
    return GoalResults(
        targets.materials.events,
        targets.materials.reader,
        spaces.fixed_adoption,
        spaces.protect_basis,
    )


def configure_conversation(spaces: CourseSpaces, configs: ActivityConfigs) -> Conversation:
    """由 Product 核对空间归属及采用，Interaction 保存活动和消息。"""

    async def authorize(
        db: AsyncConnection, account: AccountView, scope: UUID, lock: bool
    ) -> AdoptionView:
        space = await spaces.row(db, scope, lock=lock)
        spaces.authorize(account, space)
        return await spaces.adopted(db, await spaces.adoption(db, space.current_adoption_ref))

    return Conversation(spaces.engine, configs.events, configs.reader, receipts, authorize)


def configure_student_turns(
    spaces: CourseSpaces,
    conversation: Conversation,
    attachments: FactAttachments,
    settings: Settings,
    configs: ActivityConfigs,
) -> StudentTurns:
    async def current_adoption(db: AsyncConnection, scope: UUID, lock: bool) -> UUID:
        return (await spaces.row(db, scope, lock=lock)).current_adoption_ref

    async def activity_config(
        scope: UUID, adoption_id: UUID, kind: ActivityType, fixed_id: UUID | None
    ) -> tuple[ConfigView | None, CourseSnapshot]:
        async with spaces.engine.connect() as db:
            adopted = await spaces.fixed_adoption(db, scope, adoption_id)
        if fixed_id is not None:
            fixed = await configs.detail(kind, fixed_id)
            if fixed.config_ref not in adopted.snapshot.activity_config_refs:
                raise ValueError("Activity configuration is outside the adopted course")
            return fixed, adopted.snapshot
        for reference in adopted.snapshot.activity_config_refs:
            resolved = await configs.fixed_config(reference)
            if resolved.definition.activity_type == kind:
                return resolved, adopted.snapshot
        return None, adopted.snapshot

    return StudentTurns(
        conversation,
        current_adoption,
        attachments,
        settings.task_queue,
        student_config(),
        activity_config,
        spaces.read_quoted_content,
    )
