"""Shared worker process; validate dependencies before publishing local readiness."""

import asyncio
import logging
import signal
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from deermind.bootstrap import runtime
from deermind.bootstrap.courses import (
    configure_conversation,
    configure_courses,
    configure_goals,
    configure_student_turns,
)
from deermind.bootstrap.database import database_lifespan
from deermind.bootstrap.domain import configure_domain, configure_task_supply
from deermind.bootstrap.domain_operation import PURPOSE, DomainAnalysisActivities
from deermind.bootstrap.evaluation import (
    configure_activity_configs,
    configure_claims,
    configure_evaluation_inputs,
    configure_targets,
)
from deermind.bootstrap.evaluation_operation import PURPOSE as EVALUATION_PURPOSE
from deermind.bootstrap.evaluation_operation import (
    EvaluationActivities,
    configure_evaluation_operation,
    evaluation_credential,
)
from deermind.bootstrap.executions import limits
from deermind.bootstrap.material_operation import material_activities
from deermind.bootstrap.materials import (
    configure_domain_analysis,
    configure_domain_intake,
    configure_intake_processing,
    configure_material_assistant,
    configure_material_intake,
    configure_materials,
)
from deermind.bootstrap.messaging import subscriptions
from deermind.bootstrap.prompts import configure_prompts
from deermind.bootstrap.services import create_worker
from deermind.bootstrap.settings import Settings
from deermind.bootstrap.student_operation import PURPOSE as STUDENT_PURPOSE
from deermind.bootstrap.student_operation import StudentActivities, configure_detection
from deermind.bootstrap.supply_operation import CHECK, GENERATE, SupplyActivities
from deermind.bootstrap.temporal import connect_temporal
from deermind.bootstrap.waits import waits
from deermind.foundation.ai.execution import Calls
from deermind.foundation.system.delivery.bridge import run_bridge
from deermind.foundation.system.executions.contracts import Registry
from deermind.foundation.system.executions.relay import run_relay
from deermind.foundation.system.logging import configure_logging
from deermind.foundation.system.waits.reconcile import run_reconciler
from deermind.infrastructure.files.check import check_storage
from deermind.infrastructure.nats.connection import MessagingSettings, connect
from deermind.infrastructure.temporal.executions import Transport
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio.api.workflowservice.v1 import DescribeNamespaceRequest

LOGGER = logging.getLogger("runtime")
READY_FILE = Path("/tmp/deermind-worker-ready")


async def run() -> None:
    """SIGTERM stops polling; unexpected worker failure exits the process."""
    READY_FILE.unlink(missing_ok=True)
    settings = Settings.from_environment()
    check_storage(settings.files_root, require_mount=settings.files_backend == "pvc")
    async with database_lifespan() as engine:
        await serve(settings, engine)


async def serve(settings: Settings, engine: AsyncEngine) -> None:
    """数据库版本检查通过后，才连接Temporal并拉取任务。"""
    prompts = configure_prompts()
    async with asyncio.timeout(15):
        client = await connect_temporal(settings, engine)
        await client.workflow_service.describe_namespace(
            DescribeNamespaceRequest(namespace=settings.temporal_namespace),
        )

    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stopped.set)

    # Blocking file I/O runs in the activity pool, not on the asyncio loop.
    with ThreadPoolExecutor(2) as workflow_executor, ThreadPoolExecutor(4) as activity_executor:
        domain = configure_domain(engine, settings.files_root, backend=settings.files_backend)
        materials, _uploads = configure_materials(engine, settings, domain)
        assistant = configure_material_assistant(engine, settings, materials)
        intake = configure_domain_intake(materials)
        analysis = configure_domain_analysis(intake, materials, settings)
        intake_results = configure_material_intake(materials)
        processing = configure_intake_processing(analysis)
        claims = configure_claims(engine, settings)
        target_definitions = configure_targets(materials, claims)
        config = configure_activity_configs(engine, settings)
        goals = configure_goals(target_definitions, config)
        _checks, spaces, _applications = configure_courses(target_definitions, config)
        evaluation = configure_evaluation_operation(
            configure_evaluation_inputs(claims, spaces), settings.task_queue, claims.reader
        )
        conversation = configure_conversation(spaces, config)
        student = configure_student_turns(
            spaces, conversation, materials.attachments, settings, config
        )
        supply, generation = configure_task_supply(
            engine, materials.events, materials.reader, materials.attachments, settings
        )
        entries = Registry(
            [
                *assistant.registry.entries.values(),
                *analysis.registry.entries.values(),
                *student.registry.entries.values(),
                *generation.registry.entries.values(),
                *evaluation.registry.entries.values(),
            ]
        )
        subscribers = subscriptions(
            intake.receive,
            intake_results.receive_result,
            processing.invalidate_source,
            goals.receive,
            supply.receive,
            evaluation.receive,
            entries=entries,
        )
        execution_limits = limits()
        calls = Calls(engine, entries, materials.attachments, prompts)
        analysis_activities = DomainAnalysisActivities(analysis, calls)
        waiting = waits(entries)

        detection = configure_detection(
            student,
            waiting,
            spaces.domain_for,
            claims.detail,
            supply.read_supplied_question,
        )
        student_activities = StudentActivities(
            student,
            calls,
            waiting,
            spaces.domain_for,
            supply.read_supplied_question,
            supply.read_fixed_question,
            detection,
        )
        supply_activities = SupplyActivities(generation, calls)
        evaluation_activities = EvaluationActivities(evaluation, calls, evaluation_credential)
        lifecycle = runtime.lifecycle(engine, entries, execution_limits)
        wait_activities = runtime.wait_activities(
            engine, waiting, timeout_seconds=execution_limits.finalize_seconds
        )
        worker = create_worker(
            client,
            settings,
            workflow_executor,
            activity_executor,
            lifecycle,
            wait_activities,
            [
                *material_activities(
                    assistant,
                    calls,
                    {
                        PURPOSE.schema_ref.model_dump_json(): PURPOSE.output,
                        STUDENT_PURPOSE.schema_ref.model_dump_json(): STUDENT_PURPOSE.output,
                        GENERATE.schema_ref.model_dump_json(): GENERATE.output,
                        CHECK.schema_ref.model_dump_json(): CHECK.output,
                        EVALUATION_PURPOSE.schema_ref.model_dump_json(): EVALUATION_PURPOSE.output,
                    },
                ),
                analysis_activities.prepare,
                analysis_activities.finish,
                student_activities.prepare,
                student_activities.prepare_mastery,
                student_activities.follow_up_mastery,
                student_activities.complete_mastery_follow_up,
                student_activities.acknowledge_answer,
                student_activities.prepare_memory,
                student_activities.save_memory,
                student_activities.detection_help,
                student_activities.review,
                student_activities.prepare_question,
                student_activities.prepare_detection,
                student_activities.finish_detection_plan,
                student_activities.finish,
                supply_activities.prepare,
                supply_activities.review,
                supply_activities.commit,
                evaluation_activities.prepare,
                evaluation_activities.save,
                evaluation_activities.publish,
            ],
        )
        try:
            async with worker, connect(MessagingSettings.from_environment()) as transport:
                await transport.check_stream(failure=False)
                await transport.check_stream(failure=True)
                # 初始化由维护入口完成；运行账号只绑定，不得建删消息资源。
                await transport.js.consumer_info(transport.settings.failures, "failure_collector")
                READY_FILE.touch()
                LOGGER.info(
                    "Worker 已启动，等待共享队列任务",
                    extra={"action": "worker_started", "outcome": "success"},
                )
                async with asyncio.TaskGroup() as tasks:
                    tasks.create_task(run_bridge(engine, transport, subscribers, stopped))
                    tasks.create_task(
                        evaluation.reconcile(stopped, execution_limits.reconcile_seconds)
                    )
                    tasks.create_task(
                        run_relay(engine, entries, Transport(client, execution_limits), stopped)
                    )
                    tasks.create_task(
                        run_reconciler(
                            engine,
                            waiting,
                            stopped,
                            interval=execution_limits.reconcile_seconds,
                            timeout_seconds=execution_limits.finalize_seconds,
                        )
                    )
        finally:
            READY_FILE.unlink(missing_ok=True)
    LOGGER.info("Worker 已停止", extra={"action": "worker_stopped", "outcome": "success"})


def main() -> None:
    configure_logging()
    try:
        asyncio.run(run())
    except Exception:
        LOGGER.exception(
            "Worker 无法继续运行，请检查配置与依赖",
            extra={"action": "worker_failed", "outcome": "failed", "error_code": "WORKER_FAILED"},
        )
        raise SystemExit(1) from None
