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
from deermind.product.materials.facts import REGISTRATION as MATERIAL_RECEIVED
from deermind.product.materials.intake_facts import REGISTRATIONS as MATERIAL_INTAKE
from deermind.spaces.domain.analysis_facts import REGISTRATIONS as DOMAIN_ANALYSIS
from deermind.spaces.domain.facts import DOMAIN_SAVED
from deermind.spaces.domain.instance_facts import REGISTRATIONS as DOMAIN_INSTANCES
from deermind.spaces.domain.intake import REGISTRATIONS as DOMAIN_INTAKE
from deermind.spaces.domain.kc_path_facts import PATH_REGISTRATIONS
from deermind.spaces.evaluation.definition_facts import REGISTRATION as CLAIM_DEFINITION
from deermind.spaces.evaluation.goal_facts import REGISTRATION as GOAL_RESULT
from deermind.spaces.interaction.config_facts import REGISTRATION as ACTIVITY_CONFIG
from sqlalchemy.ext.asyncio import AsyncEngine

REGISTRATIONS = [
    LEARNING_TARGET,
    GOAL_RESULT,
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
    ACTIVITY_CONFIG,
    *AI_REGISTRATIONS,
]


def event_store() -> EventStore:
    return EventStore(REGISTRATIONS, arrange_delivery=Outbox(subscriptions()).arrange)


def event_reader(engine: AsyncEngine, files: FileStorage) -> EventReader:
    return EventReader(engine, files, REGISTRATIONS)
