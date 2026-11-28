"""装配评价定义、领域固定版本读取和业务收据。"""

from deermind.bootstrap.events import event_reader, event_store
from deermind.bootstrap.settings import Settings
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.infrastructure.files.local import LocalFiles
from deermind.product.learning.course_spaces import CourseSpaces
from deermind.product.learning.targets import TargetDefinitions
from deermind.product.materials.receiving import MaterialReceiving
from deermind.product.persistence import receipts
from deermind.spaces.domain.evaluation_references import read_fixed_reference
from deermind.spaces.domain.instances import evaluation_task
from deermind.spaces.evaluation.assessment_models import require_members
from deermind.spaces.evaluation.basis import EvaluationBasis
from deermind.spaces.evaluation.conditions import resolve_conditions
from deermind.spaces.evaluation.definitions import ClaimDefinitions
from deermind.spaces.evaluation.inputs import EvaluationInputs
from deermind.spaces.evaluation.public import AspectRule
from deermind.spaces.interaction.configurations import ActivityConfigs
from deermind.spaces.interaction.evaluation_basis import EvaluationFacts
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncEngine


def configure_claims(engine: AsyncEngine, settings: Settings) -> ClaimDefinitions:
    files = LocalFiles(settings.files_root, backend=settings.files_backend)
    return ClaimDefinitions(
        engine,
        event_store(),
        event_reader(engine, files),
        FactAttachments(engine, files),
        receipts,
        evaluation_task,
    )


def configure_evaluation_basis(claims: ClaimDefinitions) -> EvaluationBasis:
    return EvaluationBasis(claims.engine, claims.reader)


def configure_activity_configs(engine: AsyncEngine, settings: Settings) -> ActivityConfigs:
    files = LocalFiles(settings.files_root, backend=settings.files_backend)
    return ActivityConfigs(
        engine, event_store(), event_reader(engine, files), FactAttachments(engine, files), receipts
    )


def configure_targets(materials: MaterialReceiving, claims: ClaimDefinitions) -> TargetDefinitions:
    def conditions(rule: AspectRule, supplied: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return resolve_conditions(rule.condition_schema, rule.default_values, supplied)

    return TargetDefinitions(materials, claims.detail, conditions, require_members)


def configure_evaluation_inputs(claims: ClaimDefinitions, spaces: CourseSpaces) -> EvaluationInputs:
    facts = EvaluationFacts(claims.reader)
    return EvaluationInputs(
        claims.engine,
        claims.events,
        claims.attachments,
        facts.read,
        spaces.fixed_adoption,
        claims.detail,
        read_fixed_reference,
        facts.prior_questions,
    )
