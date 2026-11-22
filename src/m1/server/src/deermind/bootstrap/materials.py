"""把教材用途与已有事件、存储和领域公开查询接线。"""

from deermind.bootstrap.domain_operation import analysis_config
from deermind.bootstrap.events import event_reader, event_store
from deermind.bootstrap.material_operation import material_config
from deermind.bootstrap.settings import Settings
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.files.uploads import FileUploads
from deermind.infrastructure.files.local import LocalFiles
from deermind.infrastructure.files.originals import inspect_original
from deermind.product.materials.adoption import MaterialAdoptions
from deermind.product.materials.assistant import MaterialAssistant
from deermind.product.materials.chapter_associations import ChapterAssociations
from deermind.product.materials.deletion import MaterialDeletion
from deermind.product.materials.intake import MaterialIntake
from deermind.product.materials.receiving import MaterialReceiving
from deermind.spaces.domain.analysis import DomainAnalysis
from deermind.spaces.domain.instance_management import InstanceManagement
from deermind.spaces.domain.instances import chapter_methods
from deermind.spaces.domain.intake import DomainIntake
from deermind.spaces.domain.intake_processing import IntakeProcessing
from deermind.spaces.domain.public import DomainService
from sqlalchemy.ext.asyncio import AsyncEngine


def configure_materials(
    engine: AsyncEngine, settings: Settings, domain: DomainService
) -> tuple[MaterialReceiving, FileUploads]:
    files = LocalFiles(settings.files_root, backend=settings.files_backend)
    uploads = FileUploads(engine, files, inspect_original)
    materials = MaterialReceiving(
        engine,
        domain,
        uploads,
        event_store(),
        event_reader(engine, files),
        FactAttachments(engine, files),
        lambda reference, limit: files.open_verified(reference, max_bytes=limit),
    )
    return materials, uploads


def configure_material_assistant(
    engine: AsyncEngine, settings: Settings, materials: MaterialReceiving
) -> MaterialAssistant:
    return MaterialAssistant(
        engine,
        materials,
        materials.events,
        materials.reader,
        materials.attachments,
        material_config(),
        settings.task_queue,
    )


def configure_material_adoptions(materials: MaterialReceiving) -> MaterialAdoptions:
    return MaterialAdoptions(materials)


def configure_chapter_associations(materials: MaterialReceiving) -> ChapterAssociations:
    return ChapterAssociations(materials, chapter_methods)


def configure_material_deletion(assistant: MaterialAssistant) -> MaterialDeletion:
    return MaterialDeletion(assistant)


def configure_material_intake(materials: MaterialReceiving) -> MaterialIntake:
    return MaterialIntake(materials)


def configure_intake_processing(analysis: DomainAnalysis) -> IntakeProcessing:
    return IntakeProcessing(analysis)


def configure_instances(analysis: DomainAnalysis) -> InstanceManagement:
    return InstanceManagement(analysis)


def configure_domain_intake(materials: MaterialReceiving) -> DomainIntake:
    return DomainIntake(materials.engine, materials.reader, materials.events)


def configure_domain_analysis(
    intake: DomainIntake,
    materials: MaterialReceiving,
    settings: Settings,
) -> DomainAnalysis:
    return DomainAnalysis(
        intake,
        materials.attachments,
        MaterialIntake(materials).require_current_source,
        analysis_config(),
        settings.task_queue,
    )
