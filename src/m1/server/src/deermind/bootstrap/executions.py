"""装配已实施业务入口和本轮确认的执行限额；不注册未来Operation占位。"""

from deermind.foundation.system.executions.contracts import Limits, Registry


def registry() -> Registry:
    """业务Workflow随所属模块注册；当前用隔离测试登记验证底座。"""
    return Registry([])


def limits() -> Limits:
    """E01-13已确认的M1起点；工作总时限仍由所属业务受理时传入。"""
    return Limits(
        request_seconds=5,
        attempts=5,
        budget_seconds=90,
        lease_seconds=30,
        reconcile_seconds=30,
        finalize_seconds=30,
    )
