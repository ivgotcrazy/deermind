"""汇总已实施事件格式；尚未实现的登记不会被静默接受。"""

from deermind.abstractions.files import FileStorage
from deermind.bootstrap.messaging import subscriptions
from deermind.foundation.ai.facts import REGISTRATIONS as AI_REGISTRATIONS
from deermind.foundation.system.delivery.facts import DELIVERY_REGISTRATION
from deermind.foundation.system.delivery.outbox import Outbox
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore
from deermind.foundation.system.executions.facts import (
    EXECUTION_REGISTRATION,
)
from deermind.foundation.system.files.records import FILE_REGISTRATION
from deermind.foundation.system.projections.contracts import REBUILD_FINISHED
from deermind.foundation.system.waits.facts import REGISTRATION as WAIT_REGISTRATION
from deermind.product.accounts.auth_facts import SIGNED_IN, SIGNED_OUT
from deermind.product.accounts.facts import ACCOUNT_REGISTRATION
from deermind.product.accounts.recovery_facts import RECOVERED
from deermind.product.accounts.usage_events import (
    USAGE_CONFIRMED,
)
from deermind.product.learning.course_facts import REGISTRATIONS as LEARNING_COURSES
from deermind.product.learning.target_facts import REGISTRATION as LEARNING_TARGET
from deermind.product.materials.adoption_facts import REGISTRATIONS as MATERIAL_ADOPTIONS
from deermind.product.materials.assistant_facts import REGISTRATIONS as MATERIAL_ASSISTANT
from deermind.product.materials.chapter_associations import REGISTRATION as CHAPTERS
from deermind.product.materials.deletion import REGISTRATION as MATERIAL_DELETION
from deermind.product.materials.edition_facts import REGISTRATION as MATERIAL_EDITION
from deermind.product.materials.facts import REGISTRATION as MATERIAL_RECEIVED
from deermind.product.materials.facts import REMOVAL as MATERIAL_ORIGINALS_REMOVED
from deermind.product.materials.intake_facts import REGISTRATIONS as MATERIAL_INTAKE
from deermind.spaces.domain.analysis_facts import REGISTRATIONS as DOMAIN_ANALYSIS
from deermind.spaces.domain.facts import DOMAIN_SAVED
from deermind.spaces.domain.instance_facts import REGISTRATIONS as DOMAIN_INSTANCES
from deermind.spaces.domain.intake import REGISTRATIONS as DOMAIN_INTAKE
from deermind.spaces.domain.kc_path_facts import PATH_REGISTRATIONS
from deermind.spaces.domain.supply_facts import REGISTRATIONS as TASK_SUPPLY
from deermind.spaces.evaluation.assessment_models import REGISTRATION as ASSESSMENT_MODEL
from deermind.spaces.evaluation.definition_facts import REGISTRATION as CLAIM_DEFINITION
from deermind.spaces.evaluation.goal_facts import REGISTRATION as GOAL_RESULT
from deermind.spaces.evaluation.input_facts import REGISTRATION as EVALUATION_INPUT
from deermind.spaces.evaluation.interpretation_facts import (
    REGISTRATION as EVALUATION_INTERPRETATION,
)
from deermind.spaces.evaluation.mastery_facts import REGISTRATION as EVALUATION_MASTERY
from deermind.spaces.interaction.config_facts import REGISTRATION as ACTIVITY_CONFIG
from deermind.spaces.interaction.conversation_facts import REGISTRATIONS as CONVERSATION
from deermind.spaces.interaction.detection_plans import REGISTRATION as DETECTION_PLAN
from deermind.spaces.interaction.help_facts import REGISTRATION as HELP_HANDLED
from deermind.spaces.interaction.memory_facts import REGISTRATION as INTERACTION_MEMORY
from deermind.spaces.interaction.provision_facts import REGISTRATIONS as TEACHING_PROVISION
from deermind.spaces.interaction.round_facts import CLOSE_REGISTRATION, START_REGISTRATION
from deermind.spaces.interaction.supply_facts import REGISTRATION as SUPPLY_REQUEST
from deermind.spaces.interaction.task_facts import REGISTRATIONS as TASK_FACTS
from sqlalchemy.ext.asyncio import AsyncEngine

REGISTRATIONS = [
    LEARNING_TARGET,
    GOAL_RESULT,
    EVALUATION_INPUT,
    EVALUATION_INTERPRETATION,
    EVALUATION_MASTERY,
    *LEARNING_COURSES,
    ACCOUNT_REGISTRATION,
    FILE_REGISTRATION,
    REBUILD_FINISHED,
    SIGNED_IN,
    SIGNED_OUT,
    USAGE_CONFIRMED,
    RECOVERED,
    DELIVERY_REGISTRATION,
    EXECUTION_REGISTRATION,
    WAIT_REGISTRATION,
    DOMAIN_SAVED,
    MATERIAL_RECEIVED,
    MATERIAL_ORIGINALS_REMOVED,
    MATERIAL_EDITION,
    *MATERIAL_ASSISTANT,
    *MATERIAL_ADOPTIONS,
    CHAPTERS,
    MATERIAL_DELETION,
    *MATERIAL_INTAKE,
    *DOMAIN_INTAKE,
    *DOMAIN_ANALYSIS,
    *DOMAIN_INSTANCES,
    *PATH_REGISTRATIONS,
    CLAIM_DEFINITION,
    ASSESSMENT_MODEL,
    ACTIVITY_CONFIG,
    *CONVERSATION,
    SUPPLY_REQUEST,
    *TASK_FACTS,
    DETECTION_PLAN,
    START_REGISTRATION,
    CLOSE_REGISTRATION,
    HELP_HANDLED,
    *TEACHING_PROVISION,
    INTERACTION_MEMORY,
    *TASK_SUPPLY,
    *AI_REGISTRATIONS,
]


def event_store() -> EventStore:
    return EventStore(REGISTRATIONS, arrange_delivery=Outbox(subscriptions()).arrange)


def event_reader(engine: AsyncEngine, files: FileStorage) -> EventReader:
    return EventReader(engine, files, REGISTRATIONS)
