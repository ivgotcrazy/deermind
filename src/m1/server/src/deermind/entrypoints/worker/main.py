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
    # ── 启动连接与停止信号 ──
    # 加载按固定身份与版本登记的提示词资源。
    prompts = configure_prompts()
    async with asyncio.timeout(15):
        # 15 秒内连接 Temporal，并核对目标命名空间可达；超时即启动失败。
        client = await connect_temporal(settings, engine)
        await client.workflow_service.describe_namespace(
            DescribeNamespaceRequest(namespace=settings.temporal_namespace),
        )

    # 停止事件：收到终止信号后置位，各后台任务据此自行退出轮询。
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stopped.set)

    # ── 线程池 ──
    # Blocking file I/O runs in the activity pool, not on the asyncio loop.
    # Workflow 任务池 2、Activity 池 4；阻塞文件 I/O 走活动线程池，不占事件循环。
    with ThreadPoolExecutor(2) as workflow_executor, ThreadPoolExecutor(4) as activity_executor:
        # ── 教材与领域侧服务 ──
        # 领域定义服务：KC/路径/对象版本的事件与附件读写。
        domain = configure_domain(engine, settings.files_root, backend=settings.files_backend)
        # 教材接收/登记服务；上传器本进程不直接使用，留空绑定。
        materials, _uploads = configure_materials(engine, settings, domain)
        # 教材助手：对话与决策，调用 AI 能力。
        assistant = configure_material_assistant(engine, settings, materials)
        # 领域侧提交读取。
        intake = configure_domain_intake(materials)
        # 领域分析：抽取/分类，必要时落生成执行。
        analysis = configure_domain_analysis(intake, materials, settings)
        # 教材业务侧入库结果接收。
        intake_results = configure_material_intake(materials)
        # 入库处理编排。
        processing = configure_intake_processing(analysis)

        # ── 学习目标与评价侧服务 ──
        # 评价主张定义：掌握度主张的登记、事实留存与读取。
        claims = configure_claims(engine, settings)
        # 学习目标定义。
        target_definitions = configure_targets(materials, claims)
        # 交互环节固定配置。
        config = configure_activity_configs(engine, settings)
        # 目标掌握度结果计算与发布。
        goals = configure_goals(target_definitions, config)
        # 学习空间与采纳；课程核对/申请本进程不直接使用，留空绑定。
        _checks, spaces, _applications = configure_courses(target_definitions, config)

        # ── 回合与供题服务 ──
        # 评价操作服务：评价输入、账本与结果发布。
        evaluation = configure_evaluation_operation(
            configure_evaluation_inputs(claims, spaces), settings.task_queue, claims.reader
        )
        # 学习空间会话：活动与消息保存。
        conversation = configure_conversation(spaces, config)
        # 学生回合服务：作答、输入、检测准备与掌握度读取。
        student = configure_student_turns(
            spaces, conversation, materials.attachments, settings, config
        )
        # 供题库存与生成执行。
        supply, generation = configure_task_supply(
            engine, materials.events, materials.reader, materials.attachments, settings
        )

        # ── 执行条目、订阅与底座依赖 ──
        # 执行条目注册表：汇总各所有者登记的执行定位信息，供生命周期/中继/等待使用。
        entries = Registry(
            [
                *assistant.registry.entries.values(),
                *analysis.registry.entries.values(),
                *student.registry.entries.values(),
                *generation.registry.entries.values(),
                *evaluation.registry.entries.values(),
            ]
        )
        # 事件订阅注册表：各模块声明关心的事件，处理器由下方活动适配器注入。
        subscribers = subscriptions(
            intake.receive,
            intake_results.receive_result,
            processing.invalidate_source,
            goals.receive,
            supply.receive,
            evaluation.receive,
            entries=entries,
        )
        # 执行限额：请求时限、尝试次数、租约与对账间隔。
        execution_limits = limits()
        # AI 调用底座：调用账本、附件读取与 prompts。
        calls = Calls(engine, entries, materials.attachments, prompts)
        # 领域分析活动适配器，挂到 Temporal Activity。
        analysis_activities = DomainAnalysisActivities(analysis, calls)
        # 等待登记服务：补查与接续的业务侧实现。
        waiting = waits(entries)

        # ── 业务活动适配器 ──
        # 检测编排：回合、活动配置与供题之间的检测准备与收尾。
        detection = configure_detection(
            student,
            waiting,
            spaces.domain_for,
            claims.detail,
            supply.read_supplied_question,
        )
        # 学生回合活动适配器：作答、记忆、检测、复习与提问等 Activity。
        student_activities = StudentActivities(
            student,
            calls,
            waiting,
            spaces.domain_for,
            supply.read_supplied_question,
            supply.read_fixed_question,
            detection,
        )
        # 供题活动适配器：固定题与生成题的准备、复核与提交。
        supply_activities = SupplyActivities(generation, calls)
        # 评价活动适配器：含凭据注入，负责准备、保存与发布。
        evaluation_activities = EvaluationActivities(evaluation, calls, evaluation_credential)

        # ── 底座活动与 Worker 注册 ──
        # 执行生命周期活动适配器：started/completed/failed 收尾。
        lifecycle = runtime.lifecycle(engine, entries, execution_limits)
        # 等待探测与接续活动适配器。
        wait_activities = runtime.wait_activities(
            engine, waiting, timeout_seconds=execution_limits.finalize_seconds
        )
        # 组装 Temporal Worker：注册 Workflow/Activity 与并发上限，绑定任务队列。
        worker = create_worker(
            client,
            settings,
            workflow_executor,
            activity_executor,
            lifecycle,
            wait_activities,
            [
                # 教材类活动：按用途 schema 映射到对应结果输出类型。
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
        # ── 启动常驻后台协程 ──
        try:
            # 启动 Worker 并连上 NATS 传输；退出时一并释放。
            async with worker, connect(MessagingSettings.from_environment()) as transport:
                # 只读核对业务流与失败流存在，不创建或删除消息资源。
                await transport.check_stream(failure=False)
                await transport.check_stream(failure=True)
                # 初始化由维护入口完成；运行账号只绑定，不得建删消息资源。
                await transport.js.consumer_info(transport.settings.failures, "failure_collector")
                # 就绪标记落盘，编排侧据此探活。
                READY_FILE.touch()
                LOGGER.info(
                    "Worker 已启动，等待共享队列任务",
                    extra={"action": "worker_started", "outcome": "success"},
                )
                async with asyncio.TaskGroup() as tasks:
                    # 消息桥接：按订阅把事件投递给对应所有者处理器。
                    tasks.create_task(run_bridge(engine, transport, subscribers, stopped))
                    # 评价对账：补查未收尾的评价操作。
                    tasks.create_task(
                        evaluation.reconcile(stopped, execution_limits.reconcile_seconds)
                    )
                    # 执行中继：对接 Temporal Transport，推进已受理执行。
                    tasks.create_task(
                        run_relay(engine, entries, Transport(client, execution_limits), stopped)
                    )
                    # 等待对账：补查遗漏通知，接续到期等待。
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
            # 退出时移除就绪标记，避免编排侧继续把流量发往本进程。
            READY_FILE.unlink(missing_ok=True)
    LOGGER.info("Worker 已停止", extra={"action": "worker_stopped", "outcome": "success"})


def main() -> None:
    configure_logging()
    try:
        asyncio.run(run())
    except Exception:
        # 未预期启动失败：记录后以非零码退出，交由编排重启。
        LOGGER.exception(
            "Worker 无法继续运行，请检查配置与依赖",
            extra={"action": "worker_failed", "outcome": "failed", "error_code": "WORKER_FAILED"},
        )
        raise SystemExit(1) from None
