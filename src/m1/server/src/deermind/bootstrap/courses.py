"""Compose the public course and Evaluation dependencies for API and Worker."""

from deermind.product.learning.course_applications import CourseApplications
from deermind.product.learning.course_checks import CourseChecks
from deermind.product.learning.course_spaces import CourseSpaces
from deermind.product.learning.targets import TargetDefinitions
from deermind.spaces.domain.course_readiness import check_methods
from deermind.spaces.evaluation.goal_results import GoalResults
from deermind.spaces.interaction.configurations import ActivityConfigs


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
