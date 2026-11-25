"""Explicit worker assembly; the SDK rejects duplicate workflow/activity names."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from deermind.bootstrap.domain_operation import DomainAnalysisWorkflow
from deermind.bootstrap.evaluation_operation import EvaluationWorkflow, TeachingWorkflow
from deermind.bootstrap.material_operation import MaterialWorkflow
from deermind.bootstrap.settings import Settings
from deermind.bootstrap.student_operation import StudentWorkflow
from deermind.bootstrap.supply_operation import SupplyWorkflow
from deermind.infrastructure.temporal.executions import Lifecycle
from deermind.infrastructure.temporal.probe import StorageProbe
from deermind.infrastructure.temporal.probe_activity import ProbeActivity
from deermind.infrastructure.temporal.waits import Activities as WaitActivities
from temporalio.client import Client
from temporalio.worker import PollerBehaviorSimpleMaximum, Worker


def create_worker(
    client: Client,
    settings: Settings,
    workflow_executor: ThreadPoolExecutor,
    activity_executor: ThreadPoolExecutor,
    lifecycle: Lifecycle | None = None,
    waits: WaitActivities | None = None,
    material: list[Callable[..., Any]] | None = None,
) -> Worker:
    """注册探测及公共生命周期；业务Workflow随所属增量接线。"""
    return Worker(
        client,
        task_queue=settings.task_queue,
        workflows=[
            StorageProbe,
            MaterialWorkflow,
            DomainAnalysisWorkflow,
            StudentWorkflow,
            SupplyWorkflow,
            EvaluationWorkflow,
            TeachingWorkflow,
        ]
        # 传入业务装配时才注册各业务 Workflow；否则只挂探测 Workflow。
        if material
        else [StorageProbe],
        activities=[ProbeActivity(settings.files_root).reply]
        + ([lifecycle.started, lifecycle.completed, lifecycle.failed] if lifecycle else [])
        + ([waits.probe, waits.handle] if waits else [])
        + (material or []),
        max_concurrent_workflow_tasks=2,
        max_concurrent_activities=4,
        max_cached_workflows=8,
        workflow_task_executor=workflow_executor,
        activity_executor=activity_executor,
        workflow_task_poller_behavior=PollerBehaviorSimpleMaximum(maximum=2),
        activity_task_poller_behavior=PollerBehaviorSimpleMaximum(maximum=2),
    )
